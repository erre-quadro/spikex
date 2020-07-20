from pathlib import Path

from igraph import Graph
from srsly import json_dumps
from wasabi import msg

from .. import __version__ as spikex_version
from ..templates.wikigraph import get_meta
from ..wikigraph import dumptools as dt
from ..wikigraph.dumptools import WIKI_CL_TYPE_PAGE
from ..wikigraph.wikigraph import KIND_CATEGORY, KIND_PAGE


def create_wikigraph(
    wiki="en",
    version="latest",
    output_path: Path = None,
    dumps_path: Path = None,
    max_workers: int = None,
    only_core: bool = None,
):
    t = "core" if only_core else "full"
    version = dt.resolve_version(wiki, version)
    if not version:
        return
    if not output_path.exists():
        output_path.mkdir()
        msg.good("Created output directory: {}".format(output_path))
    if any(p for p in output_path.iterdir()):
        msg.fail(
            "Output directory is not empty",
            "Please use an empty directory or a different path instead. If "
            "the specified output path doesn't exist, the directory will be "
            "created for you.",
            exits=1,
        )
    graph_name = f"{wiki}wiki_{t}"
    graph_path = output_path.joinpath(graph_name)
    if not graph_path.exists():
        graph_path.mkdir()
    graph_format = "picklez"
    graph_filename = f"{graph_name}.{graph_format}"
    graph_filepath = graph_path.joinpath(graph_filename)
    kwargs = {
        "dumps_path": dumps_path,
        "max_workers": max_workers,
        "wiki": wiki,
        "version": version,
        "verbose": True,
    }
    g = Graph(directed=True)
    g = _make_graph_vertices(g, only_core, **kwargs)
    g = _make_graph_edges(g, only_core, **kwargs)
    with msg.loading("saving graph..."):
        g.write(graph_filepath)
    meta = get_meta()
    meta["name"] = graph_name
    meta["format"] = graph_format
    meta["version"] = version
    meta["spikex_version"] = f">={spikex_version}"
    meta["fullname"] = f"{graph_name}-{spikex_version}"
    meta["sources"].append("Wikipedia")
    meta_path = graph_path.joinpath("meta.json")
    meta_path.write_text(json_dumps(meta, indent=2))
    msg.good(f"Successfully created {graph_name}.")


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
    iter_cl_data = dt.iter_categorylinks_dump_data(**kwargs)
    for cl_type, sourceid, target_title in iter_cl_data:
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
        vertices = set(t2v.values())
        diff = set.difference(vertices, cats_with_pages)
        g.delete_vertices(diff)
    return g
