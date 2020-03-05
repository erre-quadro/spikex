import pytest

from respacy.labeller import Labeller


@pytest.fixture
def labellings():
    return [
        {"label": "TEST", "pattern": [{"TEXT": "test"}]},
        {"label": "NO_TEST", "pattern": [{"TEXT": "test", "OP": "!"}]},
    ]


def test_from_static_constructor(nlp, labellings):
    labeller = Labeller.from_labellings(labellings)
    doc = nlp("This is a test")
    matches = labeller(doc)
    assert len(matches) == 4
    assert len(doc._.labellings) == 4
    assert doc[0]._.labels[0] == "NO_TEST"
    assert doc[-1]._.labels[0] == "TEST"
