import shutil
from distutils.dir_util import copy_tree
from os import rename
from pathlib import Path

from srsly import json_loads
from wasabi import msg

from ..templates.wikigraph import pkg_path


def package_wikigraph(input_path: Path, output_path: Path, force: bool = None):
    """
    Generate an installable Python package for a `WikiGraph`.

    After packaging, "python setup.py sdist" must be run in the package directory,
    which will create a .tar.gz archive that can be installed via "pip install".

    Parameters
    ----------
    input_path : Path
        [description]
    output_path : Path
        [description]
    force : bool, optional
        [description], by default None
    """
    if not input_path or not input_path.exists():
        msg.fail("Can't locate graph data", input_path, exits=1)
    if not output_path:
        msg.fail("Output directory is missing", output_path, exits=1)
    if not output_path.exists():
        output_path.mkdir()
        msg.good("Created output directory: {}".format(output_path))
    meta_path = input_path / "meta.json"
    if not meta_path.exists():
        msg.fail("Can't find graph meta.json", meta_path, exits=1)
    meta = json_loads(meta_path.read_text())
    graph_fullname = meta["fullname"]
    package_path = output_path / graph_fullname
    if package_path.exists():
        if not force:
            msg.fail(
                "Package directory already exists",
                "Please delete the directory and try again, or use the "
                "`--force` flag to overwrite existing "
                "directories.".format(path=package_path),
                exits=1,
            )
        shutil.rmtree(package_path)
    package_path.mkdir()
    shutil.copy(meta_path, package_path)
    copy_tree(str(pkg_path), str(package_path))
    graph_name = meta["name"]
    rename(package_path / "graph-name", package_path / graph_name)
    module_path = package_path / graph_name
    copy_tree(str(input_path), str(module_path / graph_fullname))
    msg.good(
        "Successfully created package {}".format(graph_name), package_path
    )
    msg.text(
        "To build the package, run `python setup.py sdist` in this directory."
    )
