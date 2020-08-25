import pytest

from spikex.kex import WikiCatchX, WikiIdentX, WikiLinkageX, WikiTopicX


@pytest.fixture
def doc(nlp):
    return nlp("An apple a day keeps the doctor away")


def test_catches(wikigraph, doc):
    doc = WikiCatchX(graph=wikigraph)(doc)
    chunks = [catch.spans[0].lower_ for catch in doc._.catches]
    assert chunks == ["an", "apple", "a", "day", "the doctor", "the", "doctor"]


def test_topics(wikigraph, doc):
    topicx = WikiTopicX(graph=wikigraph)
    doc = topicx(doc)
    assert len(doc._.topics) == 9
    titles = set([topicx.wg.get_vertex(p)["title"] for p, _ in doc._.topics])
    assert titles == set(
        [
            "Apples",
            "Basic_English_850_words",
            "Basic_English",
            "Fruits",
            "Rosaceae",
            "Rosales",
            "Time",
            "Units_of_measurement",
            "Units_of_time",
        ]
    )


def test_idents(wikigraph, doc):
    doc = WikiIdentX(graph=wikigraph)(doc)
    chunks = [ident[0].lower_ for ident in doc._.idents]
    assert chunks == ["an", "apple", "a", "day", "the"]


def test_linkage(wikigraph, doc, nlp):
    topicx = WikiTopicX(graph=wikigraph)
    linkagex = WikiLinkageX(topicx)
    doc2 = nlp("Pear juice is very tasty")
    doc3 = nlp("Megatron is a Transformers")
    linkagex([doc, doc2, doc3])
    assert doc._.linkage
    assert doc2._.linkage
    assert doc3._.linkage
