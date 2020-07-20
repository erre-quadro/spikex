import pytest

from spikex.kex import WikiCatchX, WikiIdentX, WikiLinkageX, WikiTopicX


@pytest.fixture
def catchx(wikigraph):
    return WikiCatchX(wikigraph)


@pytest.fixture
def topicx(catchx):
    return WikiTopicX(catchx)


@pytest.fixture
def doc(nlp):
    return nlp("This is a test for knowledge extraction.")


@pytest.fixture
def expect_chunks():
    return ["test", "knowledge"]


def test_catches(doc, catchx, expect_chunks):
    catchx(doc)
    assert len(doc._.catches) == len(expect_chunks)
    chunks = [catch.spans[0].text for catch in doc._.catches]
    assert chunks == expect_chunks


def test_idents(doc, catchx, topicx, expect_chunks):
    identx = WikiIdentX(catchx, topicx)
    identx(doc)
    assert len(doc._.idents) == len(expect_chunks)
    chunks = [ident[0].text for ident in doc._.idents]
    assert chunks == expect_chunks


@pytest.mark.skip
def test_linkage(nlp, topicx):
    linkagex = WikiLinkageX(topicx)
    doc1 = nlp("A sentence partially related to something")
    doc2 = nlp("A sentence related maybe or maybe not")
    linkagex([doc1, doc2])
    print(doc1._.linkage)
    print(doc2._.linkage)


@pytest.mark.skip
def test_topics(doc, topicx):
    topicx(doc)
    for page, count in doc._.topics.items():
        print(topicx.wg.get_head_vertex(page)["title"], "-", count)
