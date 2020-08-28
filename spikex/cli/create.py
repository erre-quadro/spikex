from pathlib import Path

from srsly import json_dumps
from wasabi import msg

from .. import __version__ as spikex_version
from ..templates.wikigraph import get_meta
from ..wikigraph import WikiGraph


def create_wikigraph(
    wiki="en",
    version="latest",
    output_path: Path = None,
    dumps_path: Path = None,
    max_workers: int = None,
    only_core: bool = None,
):
    t = "core" if only_core else "full"
    if not output_path.exists():
        output_path.mkdir()
        msg.good("Created output directory: {}".format(output_path))
    if any(p.is_dir() for p in output_path.iterdir()):
        msg.fail(
            "Output directory is not empty",
            "Please use an empty directory or a different path instead. If "
            "the specified output path doesn't exist, the directory will be "
            "created for you.",
            exits=1,
        )
    kwargs = {
        "dumps_path": dumps_path,
        "max_workers": max_workers,
        "wiki": wiki,
        "version": version,
        "verbose": True,
    }
    wg = WikiGraph.build(only_core=only_core, **kwargs)
    graph_name = f"{wg.wiki}wiki_{t}"
    graph_path = output_path.joinpath(graph_name)
    if not graph_path.exists():
        graph_path.mkdir()
    graph_format = "picklez"
    with msg.loading("dumping..."):
        wg.dump(graph_path, graph_format=graph_format)
    meta = get_meta()
    meta["name"] = graph_name
    meta["version"] = wg.version
    meta["graph_format"] = graph_format
    meta["spikex_version"] = f">={spikex_version}"
    meta["fullname"] = f"{graph_name}-{spikex_version}"
    meta["sources"].append("Wikipedia")
    meta_path = graph_path.joinpath("meta.json")
    meta_path.write_text(json_dumps(meta, indent=2))
    msg.good(f"Successfully created {graph_name}.")
