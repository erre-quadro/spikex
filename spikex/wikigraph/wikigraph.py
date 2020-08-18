import importlib
from itertools import combinations, product
from typing import Iterable, Union

import regex as re
from cyac import Trie
from igraph import Graph, Vertex
from srsly import pickle_loads

from . import dumptools as dt
from .dumptools import WIKI_NS_KIND_CATEGORY, WIKI_NS_KIND_PAGE

KIND_CATEGORY = WIKI_NS_KIND_CATEGORY
KIND_PAGE = WIKI_NS_KIND_PAGE

VertexType = Union[Vertex, int]


class WikiGraph:
    def __init__(self):
        self.g = Graph(directed=True)
        self._t2p = {}
        self._t = Trie(ignore_case=True)

    def __getstate__(self):
        return (self.g, self._t, self._t2p)

    def __setstate__(self, state):
        self.g, self._t, self._t2p = state

    @staticmethod
    def load(graph_name):
        kls = importlib.import_module(graph_name)
        return pickle_loads(kls.path)

    @staticmethod
    def build(**kwargs):
        kwargs["version"] = dt.resolve_version(
            kwargs["wiki"], kwargs["version"]
        )
        wg = WikiGraph()
        _make_graph_edges(wg.g, **kwargs)
        _make_graph_vertices(wg.g, **kwargs)
        wg.build_pages_trie()
        return wg

    def build_pages_trie(self):
        t2id = {}
        for page in self.pages():
            norm_title = _normalize_title(page["title"])
            if norm_title not in t2id:
                id_ = self._t.insert(norm_title)
                t2id[norm_title] = id_
                self._t2p[id_] = set()
            id_ = t2id[norm_title]
            self._t2p[id_].add(page.index)

    def pages(self):
        yield from self.g.vs.select(kind_eq=KIND_PAGE)

    def categories(self):
        yield from self.g.vs.select(kind_eq=KIND_CATEGORY)

    def find_pages(self, text: str):
        ac_sep = set([ord(p) for p in re.findall(r"\p{P}", text)])
        for id_, start_idx, end_idx in self._pages_trie.match_longest(
            text, ac_sep
        ):
            yield (start_idx, end_idx, self._trieid2pages[id_])

    def find_vertex(self, title: str):
        return self.g.vs.find(title=title)

    def get_vertex(self, vertex: Union[int, str]):
        return self.g.vs[vertex] if isinstance(vertex, int) else vertex

    def get_head_vertex(self, vertex: VertexType):
        return self.get_redirect(vertex) or self.get_vertex(vertex)

    def is_redirect(self, vertex: VertexType):
        vx = self.get_vertex(vertex)
        return len(vx["redirect"]) > 0

    def get_redirect(self, vertex: VertexType):
        vx = self.get_vertex(vertex)
        if not self.is_redirect(vx):
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

    def get_children(
        self,
        vertex: VertexType,
        only_cats: bool = None,
        only_pages: bool = None,
    ):
        vx = self.get_head_vertex(vertex)
        if only_cats or only_pages:
            return [
                child
                for child in vx.neighbors(mode="IN")
                if (only_cats and child["kind"] == KIND_CATEGORY)
                or (only_pages and child["kind"] == KIND_PAGE)
            ]
        return vx.neighbors(mode="IN")

    def get_siblings(
        self,
        vertex: VertexType,
        only_cats: bool = None,
        only_pages: bool = None,
    ):
        return [
            child
            for parent in self.get_parents(vertex)
            for child in self.get_children(
                parent, only_cats=only_cats, only_pages=only_pages
            )
        ]

    def get_neighborhood(
        self,
        vertices: Union[Iterable[VertexType], VertexType],
        order: int = None,
        only_cats: bool = None,
        only_pages: bool = None,
    ):
        nbh = self.g.neighborhood(vertices=vertices, order=order or 1)
        filter_func = lambda x: (
            (only_cats is None or self.g.vs[x]["kind"] == KIND_CATEGORY)
            and (only_pages is None or self.g.vs[x]["kind"] == KIND_PAGE)
        )
        if not only_cats and not only_pages:
            return nbh
        if any(not isinstance(el, list) for el in nbh):
            return [el for el in nbh if filter_func(el)]
        return [[nb for nb in el if filter_func(nb)] for el in nbh]

    def get_neighborcats(
        self,
        vertices: Union[Iterable[VertexType], VertexType],
        large: bool = None,
    ):
        single_vertex = not isinstance(vertices, Iterable)
        if single_vertex:
            vertices = [vertices]
        nbcats = []
        for vertex in vertices:  # type: ignore
            vx_nbcats = set()
            for child in self.get_children(vertex):
                vx_nbcats.add(child.index)
            for parent in self.get_parents(vertex):
                vx_nbcats.add(parent.index)
                if not large:
                    continue
                for child in self.get_children(parent, only_cats=True):
                    vx_nbcats.add(child.index)
                for grand_parent in self.get_parents(parent):
                    vx_nbcats.add(grand_parent.index)
            nbcats.append(list(vx_nbcats))
        if single_vertex:
            return nbcats[0]
        return nbcats

    def get_most_similar(
        self,
        vs1: Iterable[VertexType],
        vs2: Iterable[VertexType],
        min_similarity=None,
    ):
        th = min_similarity or 0.0
        pairs = list(product(vs1, vs2))
        sims = self.g.similarity_dice(pairs=pairs)
        return [
            (
                el1 if isinstance(el1, int) else el1.index,
                el2 if isinstance(el2, int) else el2.index,
                sim,
            )
            for (el1, el2), sim in zip(pairs, sims)
            if sim > th
        ]

    def get_clusters(
        self, vertices: Iterable[VertexType], min_similarity: float = None,
    ):
        linkage = {}
        th = min_similarity or 0.0
        pairs = list(combinations(vertices, 2))
        sims = self.g.similarity_dice(pairs=pairs)
        for (el1, el2), sim in zip(pairs, sims):
            if sim <= th:
                continue
            src = el1 if isinstance(el1, int) else el1.index
            dst = el2 if isinstance(el2, int) else el2.index
            mts = linkage.setdefault(src, {})
            mts.setdefault(dst)
        seen = set()
        clusters = []
        for el1, mts in linkage.items():
            cluster = set([el1])
            adding = set(mts.keys())
            while adding and len(adding) > 0:
                el2 = adding.pop()
                if el2 in seen:
                    continue
                seen.add(el2)
                cluster.add(el2)
                if el2 not in linkage:
                    continue
                adding.update(linkage[el2].keys())
            clusters.append(cluster)
        vxs = set(
            vertices
            if any(isinstance(v, int) for v in vertices)
            else [v.index for v in vertices]  # type: ignore
        )
        singles = [{v} for v in set.difference(vxs, seen)]
        return clusters + singles


def _make_graph_vertices(g, **kwargs):
    props = {}
    for pageid, prop, value in dt.iter_page_props_dump_data(**kwargs):
        page_props = props.setdefault(pageid, {})
        page_props.setdefault(prop, value)
    page_t2pid = {}
    only_core = "only_core" in kwargs and kwargs["only_core"]
    for ns_kind, pageid, title in dt.iter_page_dump_data(**kwargs):
        wikidata = ""
        if pageid in props:
            page_props = props[pageid]
            if only_core and (
                "hiddencat" in page_props
                or "disambiguation" in page_props
                or "noindex" in page_props
            ):
                continue
            if "wikibase_item" in page_props:
                wikidata = page_props["wikibase_item"]
        g.add_vertex(
            pageid, kind=ns_kind, title=title, redirect="", wikidata=wikidata
        )
        if ns_kind == KIND_PAGE:
            page_t2pid[title] = pageid
    for sourceid, target_title in dt.iter_redirect_dump_data(**kwargs):
        try:
            source_vertex = g.vs.find(sourceid)
            targetid = page_t2pid[target_title]
        except (KeyError, ValueError):
            continue
        source_vertex["redirect"] = targetid
    return g


def _make_graph_edges(g, **kwargs):
    edges = []
    cats_with_pages = set()
    filtr = lambda x: x["kind"] == KIND_CATEGORY
    t2v = {v["title"]: v for v in g.vs.select(filtr)}
    iter_cl_data = dt.iter_categorylinks_dump_data(**kwargs)
    for cl_type, sourceid, target_title in iter_cl_data:
        try:
            source_vertex = g.vs.find(sourceid)
            target_vertex = t2v[target_title]
        except (KeyError, ValueError):
            continue
        if cl_type == dt.WIKI_CL_TYPE_PAGE:
            cats_with_pages.add(target_vertex)
        edges.append((source_vertex, target_vertex))
    g.add_edges(edges)
    if "only_core" in kwargs and kwargs["only_core"]:
        vertices = set(t2v.values())
        diff = set.difference(vertices, cats_with_pages)
        g.delete_vertices(diff)
    return g


def _normalize_title(title: str):
    open_at = title.find("(")
    if open_at < 0:
        return title
    close_at = title.find(")", open_at)
    if close_at < 0:
        return title
    a = title[: open_at - 1]
    b = title[close_at + 1 :]
    return "".join((a, b)).lower()
