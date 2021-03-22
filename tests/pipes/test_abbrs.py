import pytest

from spikex.pipes.abbrs import AbbrX, find_abbreviation


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
def abbrx(en_vocab):
    return AbbrX(en_vocab)


@pytest.mark.parametrize(
    "short",
    [
        ("(asa)"),
        ("ASA"),
        ("(as-9a)"),
        ("(AS-9A)"),
    ],
)
def test_acronyms_base(nlp, short):
    text = "this is another short abbreviation"
    long_words = _get_long_form(nlp, text, short).text.split()
    assert long_words == text.split()[-3:]


@pytest.mark.parametrize(
    "short",
    [
        ("(asa)"),
        ("ASA"),
    ],
)
def test_acronyms_with_middle_words(nlp, short):
    text = "this is another short in abbreviation"
    long_words = _get_long_form(nlp, text, short).text.split()
    assert long_words == text.split()[-4:]


@pytest.mark.parametrize(
    "short",
    [
        ("- (asa)"),
        ("- ASA"),
        ("-- (ASA)"),
    ],
)
def test_acronyms_with_end_no_alnum(nlp, short):
    text = "yet another short abbreviation"
    long_words = _get_long_form(nlp, text, short).text.split()
    assert long_words == text.split()[-3:]


@pytest.mark.parametrize(
    "short",
    [("(asa)"), ("ASA"), ("-- (ASA)")],
)
def test_acronyms_bad_long_form(nlp, short):
    text = "this is not our short abbreviation"
    assert _get_long_form(nlp, text, short) == None


@pytest.mark.parametrize("short", [("(asbrv)"), ("ASBRV"), ("TSO")])
def test_acronyms_bad_short_form(nlp, short):
    text = "this is a short abbreviation"
    assert _get_long_form(nlp, text, short) == None


@pytest.mark.parametrize(
    "short",
    [
        ("(abbrv)"),
        ("ABBRV"),
        ("(abb-9rv)"),
    ],
)
def test_abbreviations_singleword_long_form(nlp, short):
    text = "abbreviation"
    assert _get_long_form(nlp, text, short).text == text


@pytest.mark.parametrize("short", [("(abbrn)"), ("ABBRN"), ("(abb-9rv)")])
def test_abbreviations_multiword_long_form(nlp, short):
    text = "more words are considered aaaabbreviation"
    long_words = _get_long_form(nlp, text, short).text.split()
    assert long_words == text.split()[-1:]


@pytest.mark.parametrize(
    "short",
    [
        ("- (abbrv)"),
        ("- ABBRV"),
        ("-- (abb-9rv)"),
    ],
)
def test_abbreviations_with_no_alnum_end(nlp, short):
    text = "abbreviation"
    assert _get_long_form(nlp, text, short).text == text


@pytest.mark.parametrize(
    "short",
    [
        ("(aebbrn)"),
        ("AEBBRN"),
    ],
)
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
def test_detection_single(abbrx, nlp, text, short, long):
    doc = abbrx(nlp(text))
    assert len(doc._.abbrs) == 1
    assert doc._.abbrs[0].text == short
    assert doc._.abbrs[0]._.long_form.text == long


def test_detection_multiple(abbrx, nlp):
    text = "This is My Abbr (MA). I like MA. This is My Another (MA)"
    doc = abbrx(nlp(text))
    assert len(doc._.abbrs) == 3
    assert all(abbr.text == "MA" for abbr in doc._.abbrs)
    assert all(
        abbr._.long_form.text == lf
        for abbr, lf in zip(doc._.abbrs, ("My Abbr", "My Abbr", "My Another"))
    )


def test_detection_with_loner(abbrx, nlp):
    doc = abbrx(nlp("too cool (TC) is cool, this is TC"))
    assert len(doc._.abbrs) == 2
    for abbr in doc._.abbrs:
        assert abbr.text == "TC"
        assert abbr._.long_form.text == "too cool"


def test_detection_with_bad_loner(abbrx, nlp):
    doc = abbrx(nlp("my abbr is cool, this is my abbr (MA)"))
    assert len(doc._.abbrs) == 1
    assert doc._.abbrs[0].text == "MA"
    assert doc._.abbrs[0]._.long_form.text == "my abbr"


@pytest.mark.parametrize(
    "text",
    [
        ("this is not an abbreviation ABB-9V"),
        ("this is not an abbreviation. (AA)"),
    ],
)
def test_detection_empty(abbrx, nlp, text):
    doc = abbrx(nlp(text))
    assert len(doc._.abbrs) == 0
