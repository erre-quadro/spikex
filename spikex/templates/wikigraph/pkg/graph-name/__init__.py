from pathlib import Path

from srsly import json_loads

_meta_path = Path(__file__).parent / "meta.json"
meta = json_loads(_meta_path.read_text())

fpf_path = _meta_path.parent / meta["fullname"] / f"fpf.{meta['format']}"
graph_path = _meta_path.parent / meta["fullname"] / f"graph.{meta['format']}"
