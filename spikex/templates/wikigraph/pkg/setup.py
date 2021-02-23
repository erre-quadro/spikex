from os import path, walk
from pathlib import Path
from shutil import copy

from setuptools import setup
from srsly import json_loads


def list_files(data_dir):
    output = []
    for root, _, filenames in walk(data_dir):
        for filename in filenames:
            if not filename.startswith("."):
                output.append(path.join(root, filename))
    output = [path.relpath(p, path.dirname(data_dir)) for p in output]
    output.append("meta.json")
    return output


def setup_package():
    root_path = Path(__file__).parent.absolute()
    meta_path = root_path / "meta.json"
    meta = json_loads(meta_path.read_text())
    graph_name = meta["name"]
    pkg_data = list_files(path.join(graph_name, meta["fullname"]))
    requirements = [f"spikex{meta['spikex_version']}"]
    copy(meta_path, path.join(graph_name))
    setup(
        name=graph_name,
        description=meta["description"],
        author=meta["author"],
        author_email=meta["email"],
        url=meta["url"],
        version=meta["version"],
        license=meta["license"],
        packages=[graph_name],
        package_data={graph_name: pkg_data},
        install_requires=requirements,
        zip_safe=False,
    )


if __name__ == "__main__":
    setup_package()
