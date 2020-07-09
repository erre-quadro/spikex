import pytest

from spike import data
from spike.wikigraph import WikiGraph


@pytest.mark.slow()
@pytest.mark.skip()
def test_download():
    enwiki_dump = "enwiki_graph_latest"
    if data.contains(enwiki_dump):
        data.delete(enwiki_dump)
    assert WikiGraph()
