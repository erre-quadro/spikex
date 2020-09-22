import importlib
import json
from itertools import combinations, product
from pathlib import Path
from typing import Iterable, Union

import regex as re
from cyac import Trie
from igraph import Graph, Vertex
from wasabi import msg

from ..util import pickle_dump, pickle_load
from . import dumptools as dt

VERTEX_KIND_CATEGORY = dt.WIKI_NS_KIND_CATEGORY
VERTEX_KIND_PAGE = dt.WIKI_NS_KIND_PAGE

EDGE_KIND_PAGE = "p"
EDGE_KIND_CATEGORY = "c"
EDGE_KIND_REDIRECT = "r"

VertexType = Union[Vertex, int]

_XP_SEPS = re.compile(r"(\p{P})")


class WikiGraph:
    def __init__(self):
        self.g = None
        self.wiki = None
        self.version = None
        self.f = FuzzyPageFinder()

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
    def load(name: Union[Path, str]):
        if isinstance(name, Path):
            if not name.exists():
                raise IOError
            data_path = name
            meta = json.load(name / "meta.json")
        elif isinstance(name, str):
            kls = importlib.import_module(name)
            data_path = kls.data_path
            meta = kls.meta
        else:
            raise IOError
        wg = WikiGraph()
        f_path = data_path / "f"
        g_path = data_path / "g"
        if not g_path.exists() or not f_path.exists():
            raise IOError
        wg.f = pickle_load(f_path)
        graph_format = meta["graph_format"]
        wg.g = Graph.Load(g_path.open("rb"), format=graph_format)
        return wg

    def dump(self, dir_path: Path, graph_format: str = None):
        pickle_dump(self.f, dir_path / "f", compress=True)
        self.g.write(dir_path / "g", graph_format or "picklez")

    def build_page_finder(self):
        self.f.build(self.pages())

    def pages(self):
        yield from self.g.vs.select(kind_eq=VERTEX_KIND_PAGE)

    def categories(self):
        yield from self.g.vs.select(kind_eq=VERTEX_KIND_CATEGORY)

    def find_vertex(self, title: str):
        return self.g.vs.find(title=title)

    def get_vertex(self, vertex: VertexType):
        return self.g.vs[vertex] if isinstance(vertex, int) else vertex

    def get_head_vertex(self, vertex: VertexType):
        return self.get_redirect_vertex(vertex) or self.get_vertex(vertex)

    def get_redirect_vertex(self, vertex: VertexType):
        vx = self.get_vertex(vertex)
        if not vx["redirect"]:
            return
        e = self.g.es.find(_source=vx, kind=EDGE_KIND_REDIRECT)
        return e.target_vertex

    def get_disambi_vertices(self, vertex: VertexType):
        vx = self.get_vertex(vertex)
        es = self.g.es.select(_source=vx, kind=EDGE_KIND_PAGE)
        return [e.target_vertex for e in es]

    def get_parent_vertices(self, vertex: VertexType):
        vx = self.get_head_vertex(vertex)
        es = self.g.es.select(_source=vx, kind=EDGE_KIND_CATEGORY)
        return [e.target_vertex for e in es]

    def get_ancestor_vertices(self, vertex: VertexType, until: int = 2):
        def get_ancs(vx, left):
            ancs = []
            left -= 1
            for parent in self.get_parent_vertices(vx):
                ancs.append(parent)
                if not left:
                    continue
                ancs += get_ancs(parent, left)
            return set(ancs)

        return list(get_ancs(vertex, until))

    def get_most_similar(
        self, vs1: Iterable[VertexType], vs2: Iterable[VertexType] = None,
    ):
        pairs = (
            list(combinations(vs1)) if vs2 is None else list(product(vs1, vs2))
        )
        sims = self.g.similarity_dice(pairs=pairs)
        return [
            (
                el1 if isinstance(el1, int) else el1.index,
                el2 if isinstance(el2, int) else el2.index,
                sim,
            )
            for (el1, el2), sim in zip(pairs, sims)
        ]

    def find_all_pages(self, text: str, ignore_case: bool = None):
        if ignore_case is not None:
            yield from self.f.find_pages(text)
        for s, e, pages in self.f.find_pages(text):
            filter_pages = []
            decap_text = text[s + 1: e].replace(" ", "_")
            for page in pages:
                vx = self.get_vertex(page)
                decap_title = _clean_title(vx["title"][1:])
                if decap_title != decap_text:
                    continue
                filter_pages.append(page)
            if filter_pages:
                yield s, e, filter_pages


class FuzzyPageFinder:
    def __init__(self, pages: Iterable[Vertex] = None):
        self._t2p = {}
        self._t = Trie(ignore_case=True)
        if pages is not None:
            self.build(pages)

    def __getstate__(self):
        return (self._t, self._t2p)

    def __setstate__(self, state):
        self._t, self._t2p = state

    def build(self, pages: Iterable[Vertex]):
        t2id = {}
        for page in pages:
            id_ = None
            title = _clean_title(page["title"])
            norm_title = title.lower()
            if norm_title not in t2id:
                id_ = self._t.insert(norm_title)
                t2id[norm_title] = id_
                self._t2p[id_] = []
            if id_ is None:
                id_ = t2id[norm_title]
            if page.index in self._t2p[id_]:
                continue
            self._t2p[id_].append(page.index)

    def find_pages(self, text: str):
        def iter_matches(source):
            ac_seps = set([ord(p) for p in _XP_SEPS.findall(source)])
            for id_, start_idx, end_idx in self._t.match_longest(
                source, ac_seps
            ):
                yield (start_idx, end_idx, self._t2p[id_])

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
            for i in range(0, tot_match_tokens):
                if i > 0:
                    start_idx += len(tokens[i - 1])
                    chunk = "".join(tokens[i:])
                for sidx, eidx, pages in iter_matches(chunk):
                    s = start_idx + sidx
                    if s >= end_idx:
                        break
                    if s in submatches:
                        continue
                    submatches.add(s)
                    yield (s, start_idx + eidx, pages)


def make_graph(**kwargs):
    page2id = {}
    g = Graph(directed=True)
    pprops = _get_pprops(**kwargs)
    verbose = "verbose" in kwargs and kwargs["verbose"]
    msg_no_print = msg.no_print
    msg.no_print = not verbose
    iter_page_data = dt.iter_page_dump_data(**kwargs)
    for ns_kind, pageid, title in iter_page_data:
        disambi = False
        wikidata = None
        if pageid in pprops:
            page_props = pprops[pageid]
            if "hiddencat" in page_props or "noindex" in page_props:
                continue
            if "disambiguation" in page_props:
                disambi = True
            if "wikibase_item" in page_props:
                wikidata = page_props["wikibase_item"]
        g.add_vertex(
            pageid,
            title=title,
            kind=ns_kind,
            redirect=False,
            disambi=disambi,
            wikidata=wikidata or "",
        )
        page2id[title] = pageid
    _add_category_link_edges(g, page2id, **kwargs)
    _add_redirect_edges(g, page2id, **kwargs)
    _add_disambi_edges(g, page2id, **kwargs)
    msg.no_print = msg_no_print
    return g


def _get_pprops(**kwargs):
    pprops = {}
    iter_pprops_data = dt.iter_page_props_dump_data(**kwargs)
    for pageid, prop, value in iter_pprops_data:
        page_props = pprops.setdefault(pageid, {})
        page_props.setdefault(prop, value)
    return pprops


def _add_category_link_edges(g, page2id, **kwargs):
    edges = []
    offset = g.ecount()
    only_core = "only_core" in kwargs and kwargs["only_core"]
    for cl_type, sourceid, target_title in dt.iter_categorylinks_dump_data(
        **kwargs
    ):
        try:
            source_vx = g.vs.find(sourceid)
            target_id = page2id[target_title]
        except (KeyError, ValueError):
            continue
        if not only_core or only_core and cl_type == dt.WIKI_CL_TYPE_PAGE:
            edges.append((source_vx["name"], target_id))
    with msg.loading("adding category edges..."):
        g.add_edges(edges)
        g.es[offset:]["kind"] = EDGE_KIND_CATEGORY


def _add_redirect_edges(g, page2id, **kwargs):
    edges = []
    offset = g.ecount()
    for sourceid, target_title in dt.iter_redirect_dump_data(**kwargs):
        try:
            source_vx = g.vs.find(sourceid)
            target_id = page2id[target_title]
        except (KeyError, ValueError):
            continue
        source_vx["redirect"] = True
        edges.append((source_vx["name"], target_id))
    with msg.loading("adding redirect edges..."):
        g.add_edges(edges)
        g.es[offset:]["kind"] = EDGE_KIND_REDIRECT


def _add_disambi_edges(g, page2id, **kwargs):
    edges = []
    offset = g.ecount()
    for sourceid, target_title in dt.iter_pagelinks_dump_data(**kwargs):
        try:
            source_vx = g.vs.find(sourceid)
            target_id = page2id[target_title]
        except (KeyError, ValueError):
            continue
        if not source_vx["disambi"]:
            continue
        edges.append((source_vx["name"], target_id))
    with msg.loading("adding page link edges..."):
        g.add_edges(edges)
        g.es[offset:]["kind"] = EDGE_KIND_PAGE


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
