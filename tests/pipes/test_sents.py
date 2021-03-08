from spacy import load

from spikex.defaults import spacy_version

if spacy_version < 3:
    from spikex.pipes import SentX

SENTS = [
    "This is a bullet list that we want to be a unique sentence:\n"
    "\ta) the first bullet;\n"
    "\tb) the second bullet;\n"
    "\tc) a bullet with nested bullets:\n"
    "\t\t1) first nested bullet;"
    "\t\t2) second nested bullet."
    "\td) last bullet.\n",
    "Paragraph title",
    "The title was misformatted with the text. ",
    "Now we try to split on abbreviations like Figs. 1 or Fig. 2. ",
    "They can create confusion, like No.42 or eg. Num. 42 or U.S.; ",
    "these are some cases, but there could it be more out there.",
]


def test_splitta():
    nlp = load("en_core_web_sm")
    if spacy_version < 3:
        nlp.add_pipe(SentX(), before="parser")
    else:
        nlp.add_pipe("sentx", before="parser")
    doc = nlp("".join(SENTS))
    assert len([s for s in doc.sents]) == len(SENTS)
