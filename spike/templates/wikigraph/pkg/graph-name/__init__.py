from pathlib import Path
from srsly import json_loads


_here_path = Path(__file__).parent
_meta_path = _here_path / "meta.json"
_meta = json_loads(_meta_path.read_text())

_graph_name = f"{_meta['name']}.{_meta['format']}"
graph_path = _here_path / _meta["fullname"] / _graph_name