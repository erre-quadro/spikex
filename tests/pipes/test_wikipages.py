from spikex.pipes import WikiPageX


def test_wikipages(wikigraph, nlp):
    wpx = WikiPageX(wikigraph)
    doc = wpx(nlp("An apple a day keeps the doctor away"))
    chunks = [wp.text.lower() for wp in doc._.wiki_spans]
    assert chunks == ["an", "apple", "a", "day", "the doctor", "the", "doctor"]
