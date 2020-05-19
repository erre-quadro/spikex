import pytest

from respacy import data
from respacy.wikigraph import WikiGraph


@pytest.mark.slow()
def test_download():
    enwiki_dump = "enwiki_graph_latest"
    if data.contains(enwiki_dump):
        data.delete(enwiki_dump)
    assert WikiGraph()
