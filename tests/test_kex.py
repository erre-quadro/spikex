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
    assert len(doc._.catches) == 2
    assert doc._.catches[0].score == 0.5


def test_idents(doc, catchx, topicx):
    identx = WikiIdentX(catchx, topicx)
    identx(doc)
    for ident in doc._.idents:
        print(ident)
        print(ident[1])
        print(identx.wg.get_head_vertex(ident[1][0][0])["title"])


def test_linkage(nlp, topicx):
    linkagex = WikiLinkageX(topicx)
    doc1 = nlp("A sentence partially related to something")
    doc2 = nlp("A sentence related maybe or maybe not")
    linkagex([doc1, doc2])
    print(doc1._.linkage)
    print(doc2._.linkage)


def test_topics(doc, topicx):
    topicx(doc)
    for page, count in doc._.topics.items():
        print(topicx.wg.get_head_vertex(page)["title"], "-", count)
