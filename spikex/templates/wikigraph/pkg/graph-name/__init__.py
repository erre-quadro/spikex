from pathlib import Path

from srsly import json_loads

_here = Path(__file__).parent
meta = json_loads((_here / "meta.json").read_text())
data_path = _here / meta["fullname"]
