from spacy.tokens import Span

from spikex.phrases import PhraseDetector


def test_np_simple(nlp):
    text = "a simple noun phrase and a second noun phrase."
    doc = PhraseDetector(nlp.vocab)(nlp(text))
    assert len(doc._.phrases) == 2
    assert doc._.phrases[0] == ("NP", Span(doc, 0, 4))
    assert doc._.phrases[1] == ("NP", Span(doc, 5, 9))


def test_np_complex(nlp):
    text = "this is the long and unexpectedly complex noun phrase."
    doc = PhraseDetector(nlp.vocab)(nlp(text))
    assert len(doc._.phrases) == 1
    assert doc._.phrases[0] == ("NP", Span(doc, 2, 9))


def test_vp_simple(nlp):
    text = "this was created obviously simple."
    doc = PhraseDetector(nlp.vocab)(nlp(text))
    assert len(doc._.phrases) == 1
    assert doc._.phrases[0] == ("VP", Span(doc, 1, 4))


def test_vp_complex(nlp):
    text = "I have been deeply trying to find."
    doc = PhraseDetector(nlp.vocab)(nlp(text))
    assert len(doc._.phrases) == 1
    assert doc._.phrases[0] == ("VP", Span(doc, 1, 5))
