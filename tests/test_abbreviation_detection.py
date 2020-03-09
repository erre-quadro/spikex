from respacy.abbreviations import find_abbreviation


def test_find_abbreviation_acronyms(nlp):
    # Base case
    doc = nlp("this is a short abbreviation (asa)")
    long_form = doc[0:5]
    short_form = doc[6:7]
    _, long_form = find_abbreviation(long_form, short_form)
    assert long_form.text == "a short abbreviation"

    # Base case - no brackets
    doc = nlp("this is a short abbreviation ASA")
    long_form = doc[0:5]
    short_form = doc[5:6]
    _, long_form = find_abbreviation(long_form, short_form)
    assert long_form.text == "a short abbreviation"

    # Long form with some extraneous words inside
    doc = nlp("this is a short in abbreviation (asa)")
    long_form = doc[0:6]
    short_form = doc[7:8]
    _, long_form = find_abbreviation(long_form, short_form)
    assert long_form.text == "a short in abbreviation"

    # Long form with some extraneous words inside - no brackets
    doc = nlp("this is a short in abbreviation ASA")
    long_form = doc[0:6]
    short_form = doc[6:7]
    _, long_form = find_abbreviation(long_form, short_form)
    assert long_form.text == "a short in abbreviation"

    # Sent starting with long form
    doc = nlp("a short abbreviation (asa)")
    long_form = doc[0:3]
    short_form = doc[4:5]
    _, long_form = find_abbreviation(long_form, short_form)
    assert long_form.text == "a short abbreviation"

    # Non alpha-numeric char between long and short
    doc = nlp("a short abbreviation - (asa)")
    long_form = doc[0:4]
    short_form = doc[5:6]
    _, long_form = find_abbreviation(long_form, short_form)
    assert long_form.text == "a short abbreviation"

    # Non alpha-numeric char between long and short - no brackets
    doc = nlp("a short abbreviation - ASA")
    long_form = doc[0:4]
    short_form = doc[4:5]
    _, long_form = find_abbreviation(long_form, short_form)
    assert long_form.text == "a short abbreviation"

    # Double non alpha-numeric chars between long and short
    doc = nlp("a short abbreviation -- (asa)")
    long_form = doc[0:4]
    short_form = doc[5:6]
    short_form, long_form = find_abbreviation(long_form, short_form)
    assert long_form.text == "a short abbreviation"

    # No match
    doc = nlp("this is not our short abbreviation - (asa)")
    long_form = doc[0:6]
    short_form = doc[8:9]
    _, long_form = find_abbreviation(long_form, short_form)
    assert long_form == None

    # No match - no brackets
    doc = nlp("this is not our short abbreviation - ASA")
    long_form = doc[0:6]
    short_form = doc[7:8]
    _, long_form = find_abbreviation(long_form, short_form)
    assert long_form == None

    # No match - dirty abbreviation
    doc = nlp("this is a short abbreviation (as-9a)")
    long_form = doc[0:5]
    short_form = doc[6:7]
    _, long_form = find_abbreviation(long_form, short_form)
    assert long_form.text == "a short abbreviation"

    # No match - dirty abbreviation, no brackets
    doc = nlp("this is a short abbreviation AS-9A")
    long_form = doc[0:5]
    short_form = doc[5:6]
    _, long_form = find_abbreviation(long_form, short_form)
    assert long_form.text == "a short abbreviation"


def test_find_sh_abbreviation(nlp):
    # Basic case
    doc = nlp("abbreviation (abbrn)")
    long = doc[0:1]
    short = doc[2:3]
    _, long_form = find_abbreviation(long, short)
    assert long_form.text == "abbreviation"

    # Basic case - no brackets
    doc = nlp("abbreviation ABBRN")
    long = doc[0:1]
    short = doc[1:2]
    _, long_form = find_abbreviation(long, short)
    assert long_form.text == "abbreviation"

    # First letter must match start of word.
    doc = nlp("aaaabbreviation (abbrn)")
    long = doc[0:1]
    short = doc[2:3]
    _, long_form = find_abbreviation(long, short)
    assert long_form.text == "aaaabbreviation"

    # Matching is greedy for first letter (are is not included).
    doc = nlp("more words are considered aaaabbreviation (abbrn)")
    long = doc[0:5]
    short = doc[6:7]
    _, long_form = find_abbreviation(long, short)
    assert long_form.text == "aaaabbreviation"

    # Non alpha-numeric char between long and short
    doc = nlp("abbreviation - (abbrn)")
    long_form = doc[0:2]
    short_form = doc[3:4]
    _, long_form = find_abbreviation(long_form, short_form)
    assert long_form.text == "abbreviation"

    # Non alpha-numeric char between long and short - no brackets
    doc = nlp("abbreviation - ABBRN")
    long_form = doc[0:2]
    short_form = doc[3:4]
    _, long_form = find_abbreviation(long_form, short_form)
    assert long_form.text == "abbreviation"

    # No match
    doc = nlp("abbreviation (aebbrn)")
    long = doc[0:1]
    short = doc[2:3]
    _, long_form = find_abbreviation(long, short)
    assert long_form is None

    # No match - dirty abbreviation
    doc = nlp("abbreviation (ab-b9rn)")
    long = doc[0:1]
    short = doc[2:3]
    _, long_form = find_abbreviation(long, short)
    assert long_form.text == "abbreviation"
