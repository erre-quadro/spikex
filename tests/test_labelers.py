import pytest

from respacy.labelers import PatternLabeler


@pytest.fixture
def labelings():
    return [
        {"label": "TEST", "patterns": [[{"TEXT": "test"}]]},
        {"label": "NO_TEST", "patterns": [[{"TEXT": "test", "OP": "!"}]]},
    ]


@pytest.fixture
def labeler(labelings, nlp):
    labeler = PatternLabeler(nlp.vocab)
    for labeling in labelings:
        labeler.add(**labeling)
    return labeler


def test_doc_labelings(labeler, nlp):
    doc = labeler(nlp("This is a test"))
    assert len(doc._.labelings) == 4
    labeling = doc._.labelings[0]
    assert labeling.start == 0
    assert labeling.end == 1
    assert labeling.label_ == "NO_TEST"


def test_token_labels(labeler, nlp):
    doc = labeler(nlp("This is a test"))
    assert len(doc[0]._.labels) == 1
    assert len(doc[-1]._.labels) == 1
    assert doc[0]._.labels[0] == "NO_TEST"
    assert doc[-1]._.labels[0] == "TEST"

