import pytest

from spike.kex import WikiCatchX, WikiIdentX, WikiLinkageX, WikiTopicX


@pytest.fixture
def catchx(wikigraph):
    return WikiCatchX(wikigraph)


@pytest.fixture
def topicx(catchx):
    return WikiTopicX(catchx)


@pytest.fixture
def doc(nlp):
    return nlp("This is a test for knowledge extraction")


def test_catches(doc, catchx):
    catchx(doc)
    print(doc._.catches)


def test_idents(doc, catchx, topicx):
    identx = WikiIdentX(catchx, topicx)


def test_linkage(nlp, topicx):
    linkagex = WikiLinkageX(topicx)


def test_topics(doc, topicx):
    pass
