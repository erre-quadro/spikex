import pytest

from spikex.abbreviations import AbbreviationDetector, find_abbreviation


def _get_long_form(nlp, text, short):
    doc = nlp(" ".join([text, short]))
    long_end = text.count(" ") + short.count(" ") + 1
    long_form = doc[0:long_end]
    short_start = long_end + short.count("(")
    short_end = short_start + 1
    short_form = doc[short_start:short_end]
    abbr = find_abbreviation(long_form, short_form)
    if abbr is not None:
        return abbr[0]
    return abbr


@pytest.fixture(scope="module")
def detector(nlp):
    return AbbreviationDetector(nlp)


@pytest.mark.parametrize(
    "short", [("(asa)"), ("ASA"), ("(as-9a)"), ("(AS-9A)"),]
)
def test_acronyms_base(nlp, short):
    text = "this is another short abbreviation"
    long_words = _get_long_form(nlp, text, short).text.split()
    assert long_words == text.split()[-3:]


@pytest.mark.parametrize("short", [("(asa)"), ("ASA"),])
def test_acronyms_with_middle_words(nlp, short):
    text = "this is another short in abbreviation"
    long_words = _get_long_form(nlp, text, short).text.split()
    assert long_words == text.split()[-4:]


@pytest.mark.parametrize("short", [("- (asa)"), ("- ASA"), ("-- (ASA)"),])
def test_acronyms_with_end_no_alnum(nlp, short):
    text = "yet another short abbreviation"
    long_words = _get_long_form(nlp, text, short).text.split()
    assert long_words == text.split()[-3:]


@pytest.mark.parametrize("short", [("(asa)"), ("ASA"), ("-- (ASA)"),])
def test_acronyms_bad_long_form(nlp, short):
    text = "this is not our short abbreviation"
    assert _get_long_form(nlp, text, short) == None


@pytest.mark.parametrize("short", [("(asbrv)"), ("ASBRV"), ("TSO")])
def test_acronyms_bad_short_form(nlp, short):
    text = "this is a short abbreviation"
    assert _get_long_form(nlp, text, short) == None


@pytest.mark.parametrize("short", [("(abbrv)"), ("ABBRV"), ("(abb-9rv)"),])
def test_abbreviations_singleword_long_form(nlp, short):
    text = "abbreviation"
    assert _get_long_form(nlp, text, short).text == text


@pytest.mark.parametrize("short", [("(abbrn)"), ("ABBRN"), ("(abb-9rv)")])
def test_abbreviations_multiword_long_form(nlp, short):
    text = "more words are considered aaaabbreviation"
    long_words = _get_long_form(nlp, text, short).text.split()
    assert long_words == text.split()[-1:]


@pytest.mark.parametrize(
    "short", [("- (abbrv)"), ("- ABBRV"), ("-- (abb-9rv)"),]
)
def test_abbreviations_with_no_alnum_end(nlp, short):
    text = "abbreviation"
    assert _get_long_form(nlp, text, short).text == text


@pytest.mark.parametrize("short", [("(aebbrn)"), ("AEBBRN"),])
def test_abbreviations_bad_short_form(nlp, short):
    text = "abbreviation"
    assert _get_long_form(nlp, text, short) == None


@pytest.mark.parametrize(
    "text, short, long",
    [
        ("this is my abbr (MA)", "MA", "my abbr"),
        ("this is other abbr OA", "OA", "other abbr"),
        ("this is TC (too cool)", "TC", "too cool"),
    ],
)
def test_detection_single(detector, nlp, text, short, long):
    doc = detector(nlp(text))
    assert len(doc._.abbreviations) == 1
    assert doc._.abbreviations[0].text == short
    assert doc._.abbreviations[0]._.long_form.text == long


def test_detection_multiple(detector, nlp):
    text = "this is my abbr (MA) and this is MA (my abbr)"
    doc = detector(nlp(text))
    assert len(doc._.abbreviations) == 2
    for abbr in doc._.abbreviations:
        assert abbr.text == "MA"
        assert abbr._.long_form.text == "my abbr"


@pytest.mark.parametrize(
    "text, short, long",
    [
        ("my abbr is cool, this is my abbr (MA)", "MA", "my abbr"),
        ("too cool (TC) is cool, this is TC", "TC", "too cool"),
    ],
)
def test_detection_with_loners(detector, nlp, text, short, long):
    doc = detector(nlp(text))
    assert len(doc._.abbreviations) == 2
    for abbr in doc._.abbreviations:
        assert abbr.text == short
        assert abbr._.long_form.text == long


@pytest.mark.parametrize("text", [("this is not an abbreviation ABB-9V")])
def test_detection_empty(detector, nlp, text):
    doc = detector(nlp(text))
    assert len(doc._.abbreviations) == 0
