import pytest
from spacy.tokens import Span

from spikex.util import idx2i, span_idx2i

_TEXT_SAMPLE = "this is a sample text useful for testing"


@pytest.mark.parametrize(
    "idx, i, slice_at",
    [
        (0, 0, 0),  # first token
        (10, 3, 2),  # central token
        (33, 7, 4),  # last token
        (4, 1, 0),  # space in prev token
        (13, 3, 2),  # middle of a token
        pytest.param(-1, 0, 0, marks=pytest.mark.xfail),  # left out of bounds
        pytest.param(40, 0, 0, marks=pytest.mark.xfail),  # right out of bounds
    ],
)
def test_idx2i(nlp, idx, i, slice_at):
    doc = nlp(_TEXT_SAMPLE)
    doc_idx = idx2i(doc, idx)
    fix_idx = idx - sum((len(t) for t in doc[:slice_at]))
    span = Span(doc, slice_at, len(doc))
    span_idx = idx2i(span, fix_idx)
    tokens = doc[slice_at:]
    tokens_idx = idx2i(tokens, fix_idx)
    fix_i = i - slice_at
    assert doc_idx == i
    assert span_idx == fix_i
    assert tokens_idx == fix_i


@pytest.mark.parametrize(
    "start_idx, end_idx, start_i, end_i, slice_at",
    [
        (0, 4, 0, 1, 0),  # first token
        (0, 7, 0, 2, 0),  # first tokens
        (10, 16, 3, 4, 2),  # central token
        (10, 21, 3, 5, 2),  # central tokens
        (33, 40, 7, 8, 4),  # last token
        (29, 40, 6, 8, 4),  # last tokens
        (4, 10, 1, 3, 0),  # start and end with space
        (13, 19, 3, 5, 2),  # start and end in middle of a token
        pytest.param(
            -1, 1, 0, 0, 0, marks=pytest.mark.xfail
        ),  # left out of bounds
        pytest.param(
            40, 41, 0, 0, 0, marks=pytest.mark.xfail
        ),  # right out of bounds
    ],
)
def test_span_idx2i(nlp, start_idx, end_idx, start_i, end_i, slice_at):
    doc = nlp(_TEXT_SAMPLE)
    doc_bounds = span_idx2i(doc, start_idx, end_idx)
    offset_idx = len(doc[:slice_at].text_with_ws)
    fix_start_idx = start_idx - offset_idx
    fix_end_idx = end_idx - offset_idx
    span = Span(doc, slice_at, len(doc))
    span_bounds = span_idx2i(span, fix_start_idx, fix_end_idx)
    tokens = doc[slice_at:]
    tokens_bounds = span_idx2i(tokens, fix_start_idx, fix_end_idx)
    assert doc_bounds == (start_i, end_i)
    fix_bounds = (start_i - slice_at, end_i - slice_at)
    assert span_bounds == fix_bounds
    assert tokens_bounds == fix_bounds
