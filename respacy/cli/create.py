from pathlib import Path

from igraph import Graph
from wasabi import msg

from respacy.wikigraph.dumptools import iter_categorylinks_dump_data

from ..wikigraph import dumptools as dt
from ..wikigraph.dumptools import WIKI_CL_TYPE_PAGE
from ..wikigraph.wikigraph import KIND_CATEGORY, KIND_PAGE


def create_wiki_xnergraph(
    lang="en",
    version="latest",
    disk_path: Path = None,
    keep_files: bool = None,
    max_workers: int = None,
    only_core: bool = None,
    overwrite: bool = None,
    save_as: str = None,
):
    t = "core" if only_core else "dump"
    graph_name = f"{lang}wiki_{t}_{version}"
    graph_ext = save_as or "picklez"
    graph_path = disk_path.joinpath(f"{graph_name}.{graph_ext}")
    if not overwrite and graph_path.exists():
        msg.fail(
            "Add `--overwrite` to replace the existing graph at disk path."
        )
        return
    kwargs = {
        "disk_path": disk_path,
        "keep_files": keep_files,
        "max_workers": max_workers,
        "lang": lang,
        "version": version,
        "verbose": True,
    }
    g = Graph(directed=True)
    g = _make_graph_vertices(g, only_core, **kwargs)
    g = _make_graph_edges(g, only_core, **kwargs)
    with msg.loading("Writing to disk..."):
        if overwrite and graph_path.exists():
            graph_path.unlink()
        g.write(graph_path)
    msg.good(f"Successfully created WikiGraph at {graph_path}")


def _make_graph_vertices(g, only_core, **kwargs):
    props = {}
    for pageid, prop, value in dt.iter_page_props_dump_data(**kwargs):
        page_props = props.setdefault(pageid, {})
        page_props.setdefault(prop, value)
    page_t2pid = {}
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


def _make_graph_edges(g, only_core, **kwargs):
    edges = []
    cats_with_pages = set()
    filtr = lambda x: x["kind"] == KIND_CATEGORY
    t2v = {v["title"]: v for v in g.vs.select(filtr)}
    for cl_type, sourceid, target_title in iter_categorylinks_dump_data(
        **kwargs
    ):
        try:
            source_vertex = g.vs.find(sourceid)
            target_vertex = t2v[target_title]
        except (KeyError, ValueError):
            continue
        if cl_type == WIKI_CL_TYPE_PAGE:
            cats_with_pages.add(target_vertex)
        edges.append((source_vertex, target_vertex))
    with msg.loading("adding edges..."):
        g.add_edges(edges)
    if only_core:
        g.delete_vertices(set.difference(set(t2v.values()), cats_with_pages))
    return g
