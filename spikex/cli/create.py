from pathlib import Path

from srsly import json_dumps
from wasabi import msg

from .. import __version__ as spikex_version
from ..templates.wikigraph import get_meta
from ..wikigraph import WikiGraph


def create_wikigraph(
    output_path: Path,
    wiki="en",
    version="latest",
    dumps_path: Path = None,
    max_workers: int = None,
    silent: bool = None,
    force: bool = None,
):
    """
    Create a `WikiGraph` from a specific dump.

    It can then be used by directly loading it, or
    it can be packaged with the `package-wikigraph` command.

    Parameters
    ----------
    output_path : Path
        Path in which to store the `WikiGraph`.
    wiki : str, optional
        Wikipedia dump type to use, by default "en".
    version : str, optional
        Wikipedia dump version to use, by default "latest".
    dumps_path : Path, optional
        Path in which to find previously downloaded dumps,
        or where to save dumps downloaded in this call, by default None.
    max_workers : int, optional
        Maximum number of processes to use, by default None.
    silent : bool, optional
        Do not print anything in stout, by default None.
    force : bool, optional
        Overwrite content in output_path, if any, by default None.
    """
    if not output_path.exists():
        output_path.mkdir()
        msg.good(f"Created output directory: {output_path}")
    graph_name = f"{wiki}wiki_core"
    graph_path = output_path.joinpath(graph_name)
    if not force and graph_path.exists():
        msg.fail(
            f"Output path already contains {graph_name} directory",
            "Use --force to overwrite it",
            exits=1,
        )
    kwargs = {
        "dumps_path": dumps_path,
        "max_workers": max_workers,
        "wiki": wiki,
        "version": version,
        "verbose": not silent,
    }
    wg = WikiGraph.build(**kwargs)
    if not graph_path.exists():
        graph_path.mkdir()
    with msg.loading("dump to disk..."):
        wg.dump(graph_path)
    spikex_ver = ".".join(spikex_version.split(".")[:2])
    meta = get_meta()
    meta["name"] = graph_name
    meta["wiki"] = wiki
    meta["version"] = wg.version
    meta["spikex_version"] = f">={spikex_ver}"
    meta["fullname"] = f"{graph_name}-{spikex_ver}"
    meta["sources"].append("Wikipedia")
    meta_path = graph_path.joinpath("meta.json")
    meta_path.write_text(json_dumps(meta, indent=2))
    msg.good(f"Successfully created {graph_name}.")
