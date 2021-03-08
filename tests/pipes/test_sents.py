from spikex.defaults import spacy_version
from spikex.pipes import SentX

if spacy_version >= 3:
    from spacy.language import Language

    @Language.factory("sentx")
    def create_sentx(nlp, name):
        return SentX()


SENTS = [
    "This is a bullet list that we want to be a unique sentence:\n"
    "\ta) the first bullet;\n"
    "\tb) the second bullet;\n"
    "\tc) a bullet with nested bullets:\n"
    "\t\t1) first nested bullet;"
    "\t\t2) second nested bullet."
    "\td) last bullet.\n",
    "Paragraph title ",
    "The title was misformatted with the text. ",
    "Now we try to split on abbreviations like Figs. 1 or Fig. 2. ",
    "They can create confusion, like No.42 or eg. Num. 42 or U.S.; ",
    "these are some cases, but there could it be more out there.",
]


def test_splitta(nlp):
    sentx_pipe = SentX() if spacy_version < 3 else "sentx"
    nlp.add_pipe(sentx_pipe, before="parser")
    doc = nlp("".join(SENTS))
    assert len([s for s in doc.sents]) == len(SENTS)
