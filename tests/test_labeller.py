import pytest

from respacy.labeller import Labeller
from spacy.tokens import Span


@pytest.fixture
def labellings():
    return [
        {"label": "TEST", "pattern": [{"TEXT": "test"}]},
        {"label": "NO_TEST", "pattern": [{"TEXT": "test", "OP": "!"}]},
    ]


@pytest.fixture
def labeller(labellings):
    return Labeller.from_labellings(labellings)    


def test_doc_labellings(labeller, nlp):
    doc = nlp("This is a test")
    matches = labeller(doc)
    assert len(doc._.labellings) == 4
    labelling = doc._.labellings[0]
    assert labelling.start == 0
    assert labelling.end == 1
    assert labelling.label_ == "NO_TEST"


def test_token_labels(labeller, nlp):
    doc = nlp("This is a test")
    matches = labeller(doc)
    assert len(doc[0]._.labels) == 1
    assert len(doc[-1]._.labels) == 1
    assert doc[0]._.labels[0] == "NO_TEST"
    assert doc[-1]._.labels[0] == "TEST"
