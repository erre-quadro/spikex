import pytest

from spike.entity_linking.wikientx import WikiEntX


@pytest.mark.slow()
@pytest.mark.skip()
def test_wiki_entx(nlp):
    wiki_entx = WikiEntX()
    doc = wiki_entx(nlp(open("resources/sample5.txt").read()), stopwords=True)
    res = {}
    for chunk in doc._.wiki_chunks:
        if chunk.text in res:
            continue
        res.setdefault(
            f"{chunk.text} ({' | '.join([t.pos_ for t in chunk])})",
            max(((e[0], e[2]) for e in chunk._.wiki_ents), key=lambda x: x[1]),
        )
    for el, e in sorted(res.items(), key=lambda x: x[1][1]):
        print("-->", el, ":", e[0]["title"], "-", e[1])
