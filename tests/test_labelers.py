from spikex.labelers import PatternLabeler


def test_labelings(nlp):
    labeler = PatternLabeler(nlp.vocab)
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
