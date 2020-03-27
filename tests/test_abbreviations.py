import pytest

from respacy.abbreviations import find_abbreviation


def _get_long_form(nlp, text, short):
    doc = nlp(" ".join([text, short]))
    long_end = text.count(" ") + short.count(" ") + 1
    long_form = doc[0:long_end]
    short_start = long_end + short.count("(")
    short_end = short_start + 1
    short_form = doc[short_start:short_end]
    return find_abbreviation(long_form, short_form)[0]


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


@pytest.mark.parametrize("short", [("(asbrv)"), ("ASBRV"), ("TSO"),])
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
def test_abbreviations_with_end_no_alnum(nlp, short):
    text = "abbreviation"
    assert _get_long_form(nlp, text, short).text == text


@pytest.mark.parametrize("short", [("(aebbrn)"), ("AEBBRN"),])
def test_abbreviations_bad_short_form(nlp, short):
    text = "abbreviation"
    assert _get_long_form(nlp, text, short) == None
