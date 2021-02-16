import pytest

from spikex.pipes.abbrs import AbbrX
from spikex.pipes.labels import LabelX


def test_simple_labels(nlp):
    labeler = LabelX(nlp.vocab)
    # first label
    labeler.add("NO_TEST", [[{"TEXT": "test", "OP": "!"}]])
    doc = labeler(nlp("This is a test"))
    assert len(doc._.labelings) == 3
    for labeling in doc._.labelings:
        assert labeling.label_ == "NO_TEST"
    # second label
    labeler.add("TEST", [[{"TEXT": "test"}]])
    doc = labeler(nlp("This is a test"))
    assert doc._.labelings[-1].label_ == "TEST"


@pytest.mark.parametrize(
    "text, label, patterns",
    (
        (
            "a antilock braking system (abs)",
            "short-to-long",
            [[{"LOWER": "abs"}]],
        ),
        (
            "a computer system (CS)",
            "long-to-short",
            [[{"LOWER": "computer"}, {"LOWER": "system"}]],
        ),
    ),
)
def test_merge_abbrs_labelings(nlp, text, label, patterns):
    abbrx = AbbrX(nlp.vocab)
    labeler = LabelX(nlp.vocab)
    labeler.add(label, patterns)
    doc = labeler(abbrx(nlp(text)))
    assert len(doc._.labelings) == 2
    assert doc._.labelings[0].label_ == label
    assert doc._.labelings[1].label_ == label


@pytest.mark.parametrize(
    "text, label, patterns",
    (
        (
            "a antilock braking system",
            "intra",
            [
                [{"LOWER": "antilock"}],
                [{"LOWER": "braking"}],
                [{"LOWER": "system"}],
                [
                    {"LOWER": "antilock"},
                    {"LOWER": "braking"},
                    {"LOWER": "system"},
                ],
            ],
        ),
        (
            "a computer system engineer",
            "inter",
            [
                [{"LOWER": "computer"}, {"LOWER": "system"}],
                [{"LOWER": "system"}, {"LOWER": "engineer"}],
            ],
        ),
    ),
)
def test_keep_longest_only(nlp, text, label, patterns):
    labeler = LabelX(nlp.vocab, only_longest=True)
    labeler.add(label, patterns)
    doc = labeler(nlp(text))
    assert len(doc._.labelings) == 1
    assert doc._.labelings[0].label_ == label
