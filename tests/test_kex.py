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
    return nlp("An apple a day keeps the doctor away")


def test_catches(doc, catchx):
    catchx(doc)
    chunks = [catch.spans[0].text for catch in doc._.catches]
    assert chunks == ["apple", "day", "doctor"]


def test_topics(doc, topicx):
    topicx(doc)
    assert len(doc._.topics) == 4
    titles = set([topicx.wg.get_vertex(p)["title"] for p in doc._.topics])
    assert titles == set(
        ["Basic_English", "Basic_English_850_words", "Units_of_time", "Apples"]
    )


def test_idents(doc, topicx):
    WikiIdentX(topicx=topicx)(doc)
    chunks = [ident[0].text for ident in doc._.idents]
    assert chunks == ["apple", "day"]


def test_linkage(doc, nlp, topicx):
    linkagex = WikiLinkageX(topicx)
    doc2 = nlp("Pear juice is very tasty")
    doc3 = nlp("Megatron is a Transformers")
    linkagex([doc, doc2, doc3])
    assert doc._.linkage
    assert doc2._.linkage
    assert doc3._.linkage
