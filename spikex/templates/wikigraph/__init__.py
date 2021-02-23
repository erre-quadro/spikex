from pathlib import Path

from srsly import json_loads

_here_path = Path(__file__).parent
pkg_path = _here_path.joinpath("pkg")


def get_meta():
    meta_path = _here_path.joinpath("meta.json")
    return json_loads(meta_path.read_bytes())
