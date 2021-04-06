import gzip
import io
from math import ceil, floor
from pathlib import Path
from typing import List, Union

import srsly
from spacy.tokens import Doc, Span, Token


def span_idx2i(
    source: Union[Doc, Span, List[Token]],
    start_idx: int,
    end_idx: int,
    maxlen: int = None,
):
    start_i = 0 if start_idx == 0 else -1
    maxlen = maxlen or (
        sum([len(t) for t in source])
        if isinstance(source, list)
        else len(source.text)
    )
    end_i = len(source) if end_idx == maxlen else -1
    if start_i >= 0 and end_i >= 0:
        return start_i, end_i
    start_i = idx2i(source, start_idx)
    if end_i >= 0:
        return start_i, end_i
    last_i = start_i
    offset_i = source[0].i
    offset_idx = source[0].idx
    for token in source[start_i:]:
        last_i = token.i - offset_i
        if token.idx - offset_idx < end_idx:
            continue
        return start_i, last_i
    token = source[last_i]
    last_idx = token.idx - offset_idx
    if end_idx < last_idx:
        return start_i, last_i
    if end_idx < last_idx + len(token):
        return start_i, last_i + 1
    return start_i, start_i + 1


def idx2i(source: Union[Doc, Span, List[Token]], idx: int):
    max_i = len(source)
    offset_idx = source[0].idx

    def _idx2i(_idx, start, end):
        if start == end:
            return start
        dhalf = (start + end) / 2
        fhalf = floor(dhalf)
        if fhalf >= max_i:
            return fhalf - 1
        if fhalf == 0:
            return 0
        chalf = ceil(dhalf)
        if chalf >= max_i:
            return chalf - 1
        fidx = source[fhalf].idx - offset_idx
        cidx = source[chalf].idx - offset_idx
        if _idx <= fidx + 1:
            coord = (fhalf, fidx)
        elif _idx >= cidx - 1:
            coord = (chalf, cidx)
        elif _idx <= fidx + len(source[fhalf]):
            _idx = fidx
            coord = (fhalf, fidx)
        elif _idx <= cidx + len(source[chalf]):
            _idx = cidx
            coord = (chalf, cidx)
        else:
            return
        if coord[1] == _idx or coord[1] - 1 == _idx:
            return coord[0]
        if coord[1] + 1 == _idx:
            return coord[0] + 1
        if coord[1] > _idx:
            return _idx2i(_idx, start, coord[0])
        else:
            return _idx2i(_idx, coord[0], end)

    return _idx2i(idx, 0, max_i)


def json_dumps(data, indent=0, sort_keys=False):
    return srsly.json_dumps(data, indent, sort_keys)


def json_dump(data, path, indent=0, sort_keys=False, compress=None):
    open = gzip.open if compress else io.open
    with open(path, "wb") as fd:
        fd.write(json_dumps(data, indent, sort_keys).encode())


def json_loads(data):
    return srsly.json_loads(data)


def json_load(path: Path):
    open = gzip.open if is_gzip_path(path) else io.open
    with open(path, "rb") as fd:
        return json_loads(fd.read())


def pickle_dumps(data, protocol=None):
    return srsly.pickle_dumps(data, protocol=protocol)


def pickle_dump(data, path, protocol=None, compress=None):
    open = gzip.open if compress else io.open
    with open(path, "wb") as fd:
        fd.write(pickle_dumps(data, protocol=protocol))


def pickle_loads(data):
    return srsly.pickle_loads(data)


def pickle_load(path: Path):
    open = gzip.open if is_gzip_path(path) else io.open
    with open(path, "rb") as fd:
        return pickle_loads(fd.read())


def is_gzip_data(data: bytes):
    if len(data) > 2:
        data = data[:2]
    return data == b"\x1f\x8b"


def is_gzip_path(path: Path):
    with path.open("rb") as fd:
        # The first two bytes of a gzip file are: 1f 8b
        return is_gzip_data(fd.read(2))
