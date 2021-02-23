import importlib
import json
import logging
from pathlib import Path
from typing import Iterable, Union

import regex as re
from cyac import AC
from igraph import Graph, Vertex
from wasabi import msg

from ..util import pickle_dump, pickle_load
from . import dumptools as dt

logging.basicConfig(
    format="%(asctime)s : %(threadName)s : %(levelname)s : %(message)s",
    level=logging.INFO,
)

VERTEX_KIND_CATEGORY = dt.WIKI_NS_KIND_CATEGORY
VERTEX_KIND_PAGE = dt.WIKI_NS_KIND_PAGE

VertexType = Union[Vertex, int]


def load(name: Union[Path, str]):
    if isinstance(name, Path):
        if not name.exists():
            raise IOError
        data_path = name
        meta_path = name / "meta.json"
        meta = json.load(meta_path.open())
    elif isinstance(name, str):
        kls = importlib.import_module(name)
        data_path = kls.data_path
        meta = kls.meta
    else:
        raise IOError
    f_path = data_path / "f"
    g_path = data_path / "g"
    if not g_path.exists() or not f_path.exists():
        raise IOError
    return WikiGraph.load(g_path, f_path, meta)


class WikiGraph:
    def __init__(self):
        self.g = None
        self.wiki = None
        self.version = None
        self._page_finder = WikiPageFinder()

    @staticmethod
    def build(**kwargs):
        wg = WikiGraph()
        wg.wiki = kwargs["wiki"]
        kwargs["version"] = dt.resolve_version(wg.wiki, kwargs["version"])
        wg.version = kwargs["version"]
        wg.g = make_graph(**kwargs)
        wg.build_page_finder()
        return wg

    @staticmethod
    def load(g_path, f_path, meta):
        wg = WikiGraph()
        wg._page_finder = pickle_load(f_path)
        graph_format = meta["graph_format"]
        wg.g = Graph.Load(g_path.open("rb"), format=graph_format)
        return wg

    def dump(self, dir_path: Path, graph_format: str = None):
        pickle_dump(self._page_finder, dir_path / "f", compress=True)
        self.g.write(dir_path / "g", graph_format or "picklez")

    def build_page_finder(self):
        self._page_finder.build(self.pages())

    def pages(self):
        yield from self.g.vs.select(kind_eq=VERTEX_KIND_PAGE)

    def categories(self):
        yield from self.g.vs.select(kind_eq=VERTEX_KIND_CATEGORY)

    def find_vertex(self, title: str):
        return self.g.vs.find(title=title)

    def get_vertex(self, vertex: VertexType):
        return self.g.vs[vertex] if isinstance(vertex, int) else vertex

    def redirect_vertex(self, vertex: VertexType):
        vx = self.get_vertex(vertex)
        if vx["redirect"] < 0:
            return vx
        return self.g.vs.find(vx["redirect"])

    def get_parent_vertices(self, vertex: VertexType):
        vx = self.redirect_vertex(vertex)
        es = self.g.es.select(_source=vx)
        return [e.target_vertex.index for e in es]

    def get_ancestor_vertices(self, vertex: VertexType, until: int = 2):
        def get_ancestors(vx, left):
            left -= 1
            ancestors = set()
            for parent in self.get_parent_vertices(vx):
                ancestors.add(parent)
                if not left:
                    continue
                ancestors.update(get_ancestors(parent, left))
            return ancestors

        return list(get_ancestors(vertex, until))

    def find_pages(self, text: str):
        yield from self._page_finder.find_pages(text)


_XP_SEPS = re.compile(r"(\p{P})")


class WikiPageFinder:
    def __init__(self, pages: Iterable[Vertex] = None):
        self._ac = None
        self._id2pages = {}
        if pages is not None:
            self.build(pages)

    def __getstate__(self):
        return (self._ac, self._id2pages)

    def __setstate__(self, state):
        self._ac, self._id2pages = state

    def build(self, pages: Iterable[Vertex]):
        key2pages = {}
        for page in pages:
            key = _clean_title(page["title"]).lower()
            key_pages = key2pages.setdefault(key, [])
            key_pages.append(page.index)
        self._ac = AC.build(key2pages.keys(), ignore_case=True)
        for key, id_ in self._ac.items():
            self._id2pages.setdefault(id_, key2pages[key])

    def find_pages(self, text: str):
        def iter_matches(source):
            ac_seps = set([ord(p) for p in _XP_SEPS.findall(source)])
            for id_, start_idx, end_idx in self._ac.match_longest(
                source, ac_seps
            ):
                yield (start_idx, end_idx, self._id2pages[id_])

        for match in iter_matches(text):
            yield match
            end_idx = match[1]
            start_idx = match[0]
            tot_match_tokens = len(_XP_SEPS.split(text[start_idx:end_idx]))
            if tot_match_tokens < 2:
                continue
            submatches = set()
            tokens = _XP_SEPS.split(text[start_idx:])
            chunk = tokens[0]
            for i in range(tot_match_tokens):
                if i > 0:
                    fix_i = i * 2
                    start_idx += len(tokens[fix_i - 1])
                    chunk = "".join(tokens[fix_i:])
                for sidx, eidx, pages in iter_matches(chunk):
                    s = start_idx + sidx
                    if s >= end_idx:
                        break
                    if s in submatches:
                        continue
                    submatches.add(s)
                    yield (s, start_idx + eidx, pages)


def make_graph(**kwargs):
    cat2id = {}
    page2idx = {}
    g = Graph(directed=True)
    pprops = _get_pprops(**kwargs)
    verbose = "verbose" in kwargs and kwargs["verbose"]
    msg_no_print = msg.no_print
    msg.no_print = not verbose
    iter_page_data = dt.iter_page_dump_data(**kwargs)
    for ns_kind, pageid, title in iter_page_data:
        disambi = False
        if pageid in pprops:
            page_props = pprops[pageid]
            if "hiddencat" in page_props or "noindex" in page_props:
                continue
            if "disambiguation" in page_props:
                disambi = True
        vx = g.add_vertex(
            pageid,
            title=title,
            kind=ns_kind,
            redirect=-1,
            disambi=disambi,
        )
        if ns_kind == dt.WIKI_NS_KIND_CATEGORY:
            cat2id[title] = pageid
        elif ns_kind == dt.WIKI_NS_KIND_PAGE:
            page2idx[title] = vx.index
    _add_redirects(g, page2idx, **kwargs)
    _add_category_links(g, page2idx.keys(), cat2id, **kwargs)
    msg.no_print = msg_no_print
    return g


def _get_pprops(**kwargs):
    pprops = {}
    iter_pprops_data = dt.iter_page_props_dump_data(**kwargs)
    for pageid, prop, value in iter_pprops_data:
        page_props = pprops.setdefault(pageid, {})
        page_props.setdefault(prop, value)
    return pprops


def _add_redirects(g, page2idx, **kwargs):
    for source_id, target_title in dt.iter_redirect_dump_data(**kwargs):
        try:
            source_vx = g.vs.find(source_id)
            target_idx = page2idx[target_title]
        except (KeyError, ValueError):
            continue
        source_vx["redirect"] = target_idx


def _add_category_links(g, pages, cat2id, **kwargs):
    edges = []
    for _, source_id, target_title in dt.iter_categorylinks_dump_data(
        **kwargs
    ):
        if target_title not in pages:
            continue
        try:
            source_vx = g.vs.find(source_id)
            if (
                source_vx["kind"] == dt.WIKI_NS_KIND_CATEGORY
                and source_vx["title"] not in pages
            ):
                continue
            target_id = cat2id[target_title]
        except (KeyError, ValueError):
            continue
        edges.append((source_vx["name"], target_id))
    with msg.loading("adding category edges..."):
        g.add_edges(edges)


def _clean_title(title: str):
    open_at = title.find("_(")
    if open_at < 0:
        return title
    close_at = title.find(")", open_at)
    if close_at < 0:
        return title
    a = title[:open_at]
    b = title[close_at + 1 :]
    return "".join((a, b))
