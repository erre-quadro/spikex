import importlib
from itertools import combinations, product
from typing import Iterable, Union

from igraph import Graph, Vertex

from .dumptools import WIKI_NS_KIND_CATEGORY, WIKI_NS_KIND_PAGE

KIND_CATEGORY = WIKI_NS_KIND_CATEGORY
KIND_PAGE = WIKI_NS_KIND_PAGE

VertexType = Union[Vertex, int]


class WikiGraph:
    def __init__(self, graph_name):
        kls = importlib.import_module(graph_name)
        self.g = Graph.Read(kls.graph_path)

    def pages(self):
        yield from self.g.vs.select(kind_eq=KIND_PAGE)

    def get_vertex(self, vertex: VertexType):
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

    def are_redirects(self, v1: VertexType, v2: VertexType):
        vx1 = self.get_vertex(v1)
        vx2 = self.get_vertex(v2)
        return (
            vx1["redirect"] == vx2["name"]
            or vx2["redirect"] == vx1["name"]
            or (
                vx1["redirect"]
                and vx2["redirect"]
                and vx1["redirect"] == vx2["redirect"]
            )
        )

    def get_parents(self, vertex: VertexType):
        vx = self.get_head_vertex(vertex)
        return vx.neighbors(mode="OUT")

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
        if not isinstance(vertices, Iterable):
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
