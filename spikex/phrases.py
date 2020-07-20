from spacy.tokens import Doc, Span

from .matcher import Matcher

NP_PATTERNS = [
    [
        {"POS": "DET", "OP": "?"},
        {"POS": {"IN": ["ADJ", "ADP", "ADV", "NOUN", "PROPN"]}, "OP": "*",},
        {"POS": {"IN": ["CONJ", "CCONJ"]}, "OP": "?"},
        {"POS": {"IN": ["ADJ", "ADP", "ADV", "NOUN", "PROPN"]}, "OP": "+",},
        {"POS": {"IN": ["NOUN", "PRON", "PROPN"]}},
    ]
]

VP_PATTERNS = [
    [
        {"POS": {"IN": ["ADV", "AUX", "VERB"]}, "OP": "+"},
        {"POS": "VERB", "OP": "+"},
        {"POS": "ADV", "OP": "*"},
    ]
]


class PhraseDetector:
    def __init__(self, vocab):
        Doc.set_extension("phrases", default=[], force=True)
        self._matcher = Matcher(vocab)
        self._matcher.add("NP", NP_PATTERNS)
        self._matcher.add("VP", VP_PATTERNS)

    def __call__(self, doc: Doc):
        phrases = []
        good_start = -1
        for key, start, end in self._matcher(doc):
            if good_start >= end:
                continue
            good_start = end
            span = Span(doc, start, end)
            tag = doc.vocab.strings[key]
            phrases.append((tag, span))
        doc._.phrases = phrases
        return doc
