import importlib
import json
from itertools import combinations, product
from pathlib import Path
from typing import Iterable, Union

import regex as re
from cyac import Trie
from igraph import Graph, Vertex

from ..util import pickle_dump, pickle_load
from . import dumptools as dt
from .dumptools import WIKI_NS_KIND_CATEGORY, WIKI_NS_KIND_PAGE

KIND_CATEGORY = WIKI_NS_KIND_CATEGORY
KIND_PAGE = WIKI_NS_KIND_PAGE

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
        wg.g = _make_graph(**kwargs)
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
        yield from self.g.vs.select(kind_eq=KIND_PAGE)

    def categories(self):
        yield from self.g.vs.select(kind_eq=KIND_CATEGORY)

    def find_vertex(self, title: str):
        return self.g.vs.find(title=title)

    def get_vertex(self, vertex: VertexType):
        return self.g.vs[vertex] if isinstance(vertex, int) else vertex

    def get_head_vertex(self, vertex: VertexType):
        return self.get_redirect(vertex) or self.get_vertex(vertex)

    def get_redirect(self, vertex: VertexType):
        vx = self.get_vertex(vertex)
        if not vx["redirect"]:
            return
        return self.g.vs.find(vx["redirect"])

    def get_parents(self, vertex: VertexType):
        vx = self.get_head_vertex(vertex)
        return vx.neighbors(mode="OUT")

    def get_ancestors(self, vertex: VertexType, until: int = 2):
        def get_ancs(vx, left):
            ancs = []
            left -= 1
            for parent in self.get_parents(vx):
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

    def find_all_pages(self, text: str):
        return self.f.find_pages(text)


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
            norm_title = _normalize_title(page["title"])
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


def _make_graph(**kwargs):
    c2idx = {}
    g = Graph(directed=True)
    pprops = _get_pprops(**kwargs)
    only_core = "only_core" in kwargs and kwargs["only_core"]
    # fix title escaping
    unescape = lambda x: x.replace("\\'", "'").replace('\\"', '"')
    iter_page_data = dt.iter_page_dump_data(**kwargs)
    for ns_kind, pageid, title in iter_page_data:
        disambi = None
        wikidata = None
        if pageid in pprops:
            page_props = pprops[pageid]
            if only_core and (
                "hiddencat" in page_props or "noindex" in page_props
            ):
                continue
            if "disambiguation" in page_props:
                disambi = "1"
            if "wikibase_item" in page_props:
                wikidata = page_props["wikibase_item"]
        title = unescape(title)
        vx = g.add_vertex(
            pageid,
            title=title,
            kind=ns_kind,
            redirect="",
            disambi=disambi or "",
            wikidata=wikidata or "",
        )
        if ns_kind == KIND_CATEGORY:
            c2idx.setdefault(title, vx.index)
    edges = []
    p2id = {}
    core_c_idxs = set()
    iter_cl_data = dt.iter_categorylinks_dump_data(**kwargs)
    for cl_type, sourceid, target_title in iter_cl_data:
        try:
            source_vx = g.vs.find(sourceid)
            target_idx = c2idx[unescape(target_title)]
        except (KeyError, ValueError):
            continue
        if cl_type == dt.WIKI_CL_TYPE_PAGE:
            core_c_idxs.add(target_idx)
            p2id.setdefault(source_vx["title"], source_vx["name"])
        edges.append((source_vx.index, target_idx))
    g.add_edges(edges)
    if only_core:
        idxs = set(c2idx.values())
        g.delete_vertices(idxs.difference(core_c_idxs))
    iter_redirect_data = dt.iter_redirect_dump_data(**kwargs)
    for sourceid, target_title in iter_redirect_data:
        try:
            source_vx = g.vs.find(sourceid)
            target_id = p2id[unescape(target_title)]
        except (KeyError, ValueError):
            continue
        source_vx["redirect"] = target_id
    return g


def _get_pprops(**kwargs):
    pprops = {}
    iter_pprops_data = dt.iter_page_props_dump_data(**kwargs)
    for pageid, prop, value in iter_pprops_data:
        page_props = pprops.setdefault(pageid, {})
        page_props.setdefault(prop, value)
    return pprops


def _normalize_title(title: str):
    open_at = title.find("_(")
    if open_at < 0:
        return title.lower()
    close_at = title.find(")", open_at)
    if close_at < 0:
        return title.lower()
    a = title[:open_at]
    b = title[close_at + 1 :]
    return "".join((a, b)).lower()
