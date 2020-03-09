import time
from math import ceil, floor
from typing import Union

from spacy.tokens import Doc, Span


def span_idx2i(
    source: Union[Doc, Span], start_idx: int, end_idx: int, maxlen: int = None
):
    start_i = 0 if start_idx == 0 else -1
    maxlen = maxlen or len(source.text)
    end_i = len(source) if end_idx == maxlen else -1
    if start_i >= 0 and end_i >= 0:
        return start_i, end_i
    start_i = idx2i(source, start_idx)
    if end_i >= 0:
        return start_i, end_i
    last_index = start_i
    for token in source[start_i:]:
        last_index = token.i
        if token.idx < end_idx:
            continue
        return start_i, token.i
    if end_i > 0:
        return start_i, end_i
    last_token = source[last_index]
    if end_idx < last_token.idx + len(last_token):
        return start_i, last_token.i + 1

    # for token in doc:
    #     if start_i < 0:
    #         if token.idx < start_idx:
    #             continue
    #         if token.idx == start_idx:
    #             start_i = token.i
    #         else:
    #             start_i = token.i - 1
    #     elif end_i < 0:
    #         if token.idx < end_idx:
    #             continue
    #         return start_i, token.i
    #     else:
    #         return start_i, end_i
    # if start_i > 0:
    #     return start_i, len(doc)


def idx2i(source: Union[Doc, Span], idx: int):
    # for token in source:
    #     if token.idx < idx:
    #         continue
    #     elif token.idx == idx:
    #         return token.i
    #     else:
    #         return token.i - 1

    max_i = len(source)

    def _idx2i(_idx, start, end):
        if start == end:
            return start
        dhalf = (start + end) / 2
        fhalf = floor(dhalf)
        if fhalf >= max_i:
            return fhalf - 1
        ftoken = source[fhalf]
        chalf = ceil(dhalf)
        if chalf >= max_i:
            return chalf - 1
        ctoken = source[chalf]
        token = None
        if _idx <= ftoken.idx + 1:
            token = ftoken
        elif _idx >= ctoken.idx - 1:
            token = ctoken
        elif _idx <= ftoken.idx + len(ftoken):
            _idx = ftoken.idx
            token = ftoken
        elif _idx <= ctoken.idx + len(ctoken):
            _idx = ctoken.idx
            token = ctoken
        else:
            return
        if token.i == 0 or token.idx == _idx or token.idx - 1 == _idx:
            return token.i
        if token.idx + 1 == _idx:
            return token.i + 1
        if token.idx > _idx:
            return _idx2i(_idx, start, token.i)
        else:
            return _idx2i(_idx, token.i, end)

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
