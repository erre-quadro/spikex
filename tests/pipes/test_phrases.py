import pytest

from spikex.pipes.phrases import NounPhraseX, VerbPhraseX


@pytest.mark.parametrize(
    "text, np_coords",
    [
        (
            "a simple noun phrase and a second noun phrase.",
            (
                (0, 4),
                (5, 9),
            ),
        ),
        ("this is the long and unexpectedly complex noun phrase.", ((2, 9),)),
        ("I am being stuck", ()),
    ],
)
def test_noun_phraser(nlp, text, np_coords):
    doc = NounPhraseX(nlp.vocab)(nlp(text))
    _check_phrases(doc._.noun_phrases, np_coords)


@pytest.mark.parametrize(
    "text, vp_coords",
    [
        ("this was created obviously simple.", ((1, 3),)),
        ("I have been deeply trying to find it.", ((1, 7),)),
        ("this simply big apple", ()),
    ],
)
def test_verb_phraser(nlp, text, vp_coords):
    doc = VerbPhraseX(nlp.vocab)(nlp(text))
    _check_phrases(doc._.verb_phrases, vp_coords)


def _check_phrases(phrases, coords):
    assert len(phrases) == len(coords)
    print(phrases)
    for phrase, coords in zip(phrases, coords):
        assert (phrase.start, phrase.end) == coords
