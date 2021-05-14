from spacy.tokens import Doc, Span, Token

from spikex.defaults import spacy_version

from ..matcher import Matcher

if spacy_version >= 3:
    from spacy.language import Language

    @Language.factory("labelx")
    def create_labelx(nlp, name):
        return LabelX()


class LabelX:
    """
    Detect labelings, which are pattern matching expressions
    linked to a specific label, in case using abbreviations and
    acronyms previously found by AbbrX pipe.

    If `only_longest` is flagged, it fixes overlapping matches
    by merging them and assigning the label of the last match.
    """

    def __init__(
        self, vocab, labelings=None, validate=None, only_longest=None
    ):
        Doc.set_extension("labelings", default=[], force=True)
        Token.set_extension("labels", default=[], force=True)
        self._matcher = Matcher(vocab, validate)
        self._only_longest = only_longest
        if not labelings or labelings is None:
            return
        for label, patterns in labelings:
            self.add(label, patterns)

    def add(self, label, patterns, on_match=None):
        """
        Add a labeling rule to the labeler.

        Parameters
        ----------
        label: str
            The label related to patterns.
        patterns: list
            The pattern matching expressions.
        on_match: callable, optional
            Callback executed on match, by default None.
        """
        self._matcher.add(label, patterns, on_match=on_match)

    def __call__(self, doc: Doc):
        """
        Collect all labels related to patterns matching tokens.
        Each token have a `labels` extension in which to store them.
        The supplied `Doc` have a `labelings` extension in which
        all labeled spans are collected.
        If the doc has abbrs, they contribute to label spans.

        Parameters
        ----------
        doc: Doc
            The doc to label over.

        Returns
        -------
        Doc
            The doc after labeling.
        """
        for key, start, end in self._matcher(doc):
            label = doc.vocab.strings[key]
            span = Span(doc, start, end, label)
            for token in span:
                if label in token._.labels:
                    continue
                token._.labels.append(label)
            doc._.labelings.append(span)
        _sort_labelings(doc)
        if doc.has_extension("abbrs"):
            _merge_abbrs_labelings(doc)
        if self._only_longest:
            _fix_overlabelings(doc)
        return doc


def _merge_abbrs_labelings(doc):
    num_labelings = len(doc._.labelings)
    chunk2label = {s.text: s.label for s in doc._.labelings}
    for abbr in doc._.abbrs:
        # first check if long form is labeled
        # and short one is not
        if (
            abbr._.long_form.text in chunk2label
            and abbr.text not in chunk2label
        ):
            label = chunk2label[abbr._.long_form.text]
            short_span = Span(doc, abbr.start, abbr.end, label)
            doc._.labelings.append(short_span)
        # otherwise check if short form is labeled
        # and long one is not
        elif (
            abbr.text in chunk2label
            and abbr._.long_form.text not in chunk2label
        ):
            lf = abbr._.long_form
            label = chunk2label[abbr.text]
            long_span = Span(doc, lf.start, lf.end, label)
            doc._.labelings.append(long_span)
    # sort labelings if there's changes only
    if num_labelings < len(doc._.labelings):
        _sort_labelings(doc)


def _fix_overlabelings(doc):
    good_labelings = set()
    for span in doc._.labelings:
        should_add_span = False
        for other_span in doc._.labelings:
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
            # merge spans overlapping
            # in a tail-head manner
            # (last label wins)
            if (
                span.start < other_span.start
                and span.end > other_span.start
                and span.end < other_span.end
            ) or (
                span.start > other_span.start
                and span.start < other_span.end
                and span.end > other_span.end
            ):
                if span.start < other_span.start:
                    start = span.start
                    end = other_span.end
                    label = other_span.label
                else:
                    start = other_span.start
                    end = span.end
                    label = span.label
                merge_span = Span(doc, start, end, label)
                good_labelings.add(merge_span)
                should_add_span = False
                break
        if should_add_span:
            good_labelings.add(span)
    doc._.labelings = list(good_labelings)


def _sort_labelings(doc):
    doc._.labelings.sort(key=lambda x: (x.start, -len(x)))
