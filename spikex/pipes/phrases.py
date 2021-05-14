from spacy.tokens import Doc, Span

from spikex.defaults import spacy_version

from ..matcher import Matcher

if spacy_version >= 3:
    from spacy.language import Language

    @Language.factory("phrasex")
    def create_phrasex(nlp, name):
        return PhraseX()


class PhraseX:
    """
    Create a custom `Doc`'s underscore extension in which stores
    matches found by applying given pattern matching expressions.
    """

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
        setattr(doc._, self._phrases_name, _fix_overlappings(phrases))
        return doc


if spacy_version >= 3:
    from spacy.language import Language

    @Language.factory("nounphrasex")
    def create_nounphrasex(nlp, name):
        return NounPhraseX()


NP_PATTERNS = [
    [
        {
            "POS": {"IN": ["ADJ", "ADV", "DET", "NUM", "PROPN"]},
            "OP": "*",
        },
        {"POS": {"IN": ["ADP", "CONJ", "CCONJ"]}, "OP": "?"},
        {
            "POS": {
                "IN": ["ADJ", "ADP", "ADV", "NOUN", "NUM", "PRON", "PROPN"]
            },
            "OP": "*",
        },
        {
            "POS": {"IN": ["NOUN", "PROPN"]},
        },
    ]
]


class NounPhraseX(PhraseX):
    """
    Detect noun phrases and assigns them at the custom underscore attribute `noun_phrases`
    """

    def __init__(self, vocab):
        super(NounPhraseX, self).__init__(vocab, "noun_phrases", NP_PATTERNS)


if spacy_version >= 3:
    from spacy.language import Language

    @Language.factory("verbphrasex")
    def create_verbphrasex(nlp, name):
        return VerbPhraseX()


VP_PATTERNS = [
    [
        {"POS": {"IN": ["ADV", "AUX", "PART", "VERB"]}, "OP": "*"},
        {"POS": {"IN": ["AUX", "VERB"]}},
    ]
]


class VerbPhraseX(PhraseX):
    """
    Detect verb phrases and assigns them at the custom underscore attribute `verb_phrases`
    """

    def __init__(self, vocab):
        super(VerbPhraseX, self).__init__(vocab, "verb_phrases", VP_PATTERNS)


def _fix_overlappings(spans):
    good_spans = set()
    for span in spans:
        should_add_span = False
        for other_span in spans:
            # good if spans are identical
            # or they aren't overlapping
            if (
                span.start == other_span.start
                and span.end == other_span.end
                or span.start >= other_span.end
                or span.end <= other_span.start
            ):
                should_add_span = True
                continue
            # exit loop as spans overlap
            # but one is larger
            if (
                span.start > other_span.start
                and span.end <= other_span.end
                or span.start >= other_span.start
                and span.end < other_span.end
            ):
                should_add_span = False
                break
        if should_add_span:
            good_spans.add(span)
    return sorted(good_spans, key=lambda x: (x.start, -len(x)))
