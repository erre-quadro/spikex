from spacy.tokens import Doc, Span

from ..matcher import Matcher


class PhraseX:
    def __init__(self, vocab, phrases_name, patterns):
        Doc.set_extension(phrases_name, default=[], force=True)
        self._phrases_name = phrases_name
        self._matcher = Matcher(vocab)
        self._matcher.add(phrases_name, patterns)

    def __call__(self, doc: Doc):
        phrases = []
        last_start = 0
        for _, start, end in self._matcher(doc):
            if last_start >= end:
                continue
            last_start = end
            span = Span(doc, start, end)
            phrases.append(span)
        phrases.sort(key=lambda x: (x.start, -len(x)))
        setattr(doc._, self._phrases_name, phrases)
        return doc


NP_PATTERNS = [
    [
        {"POS": {"IN": ["ADJ", "ADV", "DET", "NUM", "PROPN"]}, "OP": "*",},
        {"POS": {"IN": ["ADP", "CONJ", "CCONJ"]}, "OP": "?"},
        {
            "POS": {
                "IN": ["ADJ", "ADP", "ADV", "NOUN", "NUM", "PRON", "PROPN"]
            },
            "OP": "+",
        },
    ]
]


class NounPhraseX(PhraseX):
    def __init__(self, vocab):
        super(NounPhraseX, self).__init__(vocab, "noun_phrases", NP_PATTERNS)


VP_PATTERNS = [[{"POS": {"IN": ["ADV", "AUX", "PART", "VERB"]}, "OP": "+"},]]


class VerbPhraseX(PhraseX):
    def __init__(self, vocab):
        super(VerbPhraseX, self).__init__(vocab, "verb_phrases", VP_PATTERNS)
