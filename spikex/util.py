import time
from math import ceil, floor
from typing import List, Union

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


class TimeTrack:
    def __enter__(self):
        self.start = time.process_time()
        self.checkpoint = self.start
        return self

    def __exit__(self, *args):
        self.end = time.process_time()
        self.interval = self.end - self.start

    def save_checkpoint(self):
        self.checkpoint = time.process_time()

    def since_checkpoint(self):
        return f"{time.process_time() - self.checkpoint: .4f}"

    def since_start(self):
        return f"{time.process_time() - self.start: .4f}"
