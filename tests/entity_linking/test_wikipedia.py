from respacy.entity_linking.wikientx import WikiEntX


def test_wiki_entx(nlp):
    wiki_entx = WikiEntX()
    wiki_entx(nlp(open("resources/sample.txt").read()))
