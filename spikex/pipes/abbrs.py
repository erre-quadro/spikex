from typing import Iterable, Optional, Set, Tuple, Union

from spacy.tokens import Doc, Span

from spikex.matcher import Matcher

from ..util import span_idx2i


class AbbrX:
    """
    *Strongly based on scispacy's AbbreviationDetector*.
    Detect abbreviations which are acronyms or by using the algorithm in
    "A simple algorithm for identifying abbreviation definitions in biomedical
    text.", (Schwartz & Hearst, 2003).

    This class sets the `._.abbrs` attribute on spaCy Doc.

    The abbreviations attribute is a `List[Span]` where each Span has the `Span._.long_form`
    attribute set to the long form definition of the abbreviation.

    Note that this class does not replace the spans, or merge them.
    """

    def __init__(self, vocab) -> None:
        Doc.set_extension("abbrs", default=[], force=True)
        Span.set_extension("long_form", default=None, force=True)

        self._matcher = Matcher(vocab)
        self._matcher.add(
            "abbrs",
            [
                # Pattern for abbreviations not enclosed in brackets
                # here we limit to alpha chars only as it could
                # get many exceptions
                [{"IS_ALPHA": True, "IS_UPPER": True, "LENGTH": {">": 1}}],
                # Pattern for abbreviations enclosed in brackets
                # here we try to allow non alpha chars too as it is
                # the more likely standard way to introduce an abbreviation
                [
                    {"TEXT": {"IN": ["(", "["]}},
                    {"OP": "+"},
                    {"TEXT": {"IN": [")", "]"]}},
                ],
            ],
        )

    def find(self, span: Span, doc: Doc) -> Tuple[Span, Set[Span]]:
        """
        Functional version of calling the matcher for a single span.
        This method is helpful if you already have an abbreviation which
        you want to find a definition for.
        """
        dummy_matches = [(-1, int(span.start), int(span.end))]
        filtered = _filter_matches(dummy_matches, doc)
        abbrs = list(self.find_matches_for(filtered, doc))

        if not abbrs:
            return span, set()
        return abbrs[0]

    def __call__(self, doc: Doc) -> Doc:
        matches = self._matcher(doc)
        matches_no_punct = set(
            [
                (
                    x[0],
                    x[1] + (1 if doc[x[1]].is_punct else 0),
                    x[2] - (1 if doc[x[2] - 1].is_punct else 0),
                )
                for x in matches
            ]
        )
        filtered = _filter_matches(matches_no_punct, doc)
        occurences = _find_matches_for(filtered, doc)

        for long_form, short_form in occurences:
            short_form._.long_form = long_form
            doc._.abbrs.append(short_form)
        return doc


def find_abbreviation(
    long_form_candidate: Span, short_form_candidate: Span
) -> Tuple[Span, Optional[Span]]:
    """
    Implements an abbreviation detection algorithm which merges an
    acronym resolution algorithm with detection algorithm based on
    "A simple algorithm for identifying abbreviation definitions in
    biomedical text.", (Schwartz & Hearst, 2003).

    Parameters
    ----------
    long_form_candidate: Span, required.
        The spaCy span for the long form candidate of the definition.
    short_form_candidate: Span, required.
        The spaCy span for the abbreviation candidate.

    Returns
    -------
    A Tuple[Span, Union[Span, None]], representing the short form
    abbreviation and the span corresponding to the long form expansion,
    or None if a match was not found.
    """
    long_form = "".join([x.text_with_ws for x in long_form_candidate])
    short_form = "".join([x.text_with_ws for x in short_form_candidate])
    long_index = len(long_form) - 1
    short_index = len(short_form) - 1
    bounds_idx = _find_abbreviation(
        long_form=long_form,
        long_index=long_index,
        short_form=short_form,
        short_index=short_index,
    )
    if not bounds_idx:
        return
    start_idx, end_idx = bounds_idx
    start, end = span_idx2i(long_form_candidate, start_idx, end_idx)
    return (
        long_form_candidate[start:end],
        short_form_candidate,
    )


def _find_abbreviation(
    *, long_form: str, long_index: int, short_form: str, short_index: int
) -> Union[Tuple[int, int], None]:
    # An abbreviation char must match the starting
    # char of a word (acronym) or an its internal one.
    # In the latter case, the next abbreviation char
    # must be another internal char of the same word
    # or its beginning. In any case, a word which have
    # matched an internal char must have been matched
    # also at its starting char. Moreover, the first char
    # of the abbreviation must be the starting char of a word.
    short_index_reset = short_index
    long_index_end = long_index  # alnum bounds
    has_internal_match = False
    jumps = {}
    while short_index >= 0 and long_index >= 0:
        # Get next abbreviation char to check
        short_char = short_form[short_index].lower()
        # Don't check non alphabetic characters
        if not short_char.isalpha():
            short_index -= 1
            continue
        long_char = long_form[long_index].lower()
        # Don't let there be many unabbreviated words
        if long_char.isspace():
            jump = jumps.setdefault(short_index, 0)
            jump += 1
            if jump > 2:
                break
            jumps[short_index] = jump
        is_starting_char = (
            True
            if long_index == 0
            else not long_form[long_index - 1].isalnum()
        )
        if long_char != short_char:
            # Shrink bounds as the long form
            # ends with non-alphanumeric chars
            if long_index == long_index_end and not long_char.isalnum():
                long_index_end -= 1
            # A word which have matched an internal char
            # must match also its starting char
            if is_starting_char and has_internal_match:
                short_index = short_index_reset
                has_internal_match = False
                continue
            long_index -= 1
            continue
        # First abbreviation char must match
        # the starting char of a word
        if short_index == 0 and not is_starting_char:
            long_index -= 1
            continue
        long_index -= 1
        short_index -= 1
        if not is_starting_char:
            has_internal_match = True
    # In case it didn't end at the starting
    # of a word, move it a step ahead
    if long_index >= 0 and not long_form[long_index].isalnum():
        long_index += 1
    # In case the abbreviation doesn't fully match
    # or it doesn't match from a starting char
    # finding fails
    if (
        short_index >= 0
        or long_index > 0
        and long_form[long_index - 1].isalnum()
    ):
        return
    long_start = max(long_index, 0)
    long_end = long_index_end + 1
    if long_start == long_end:
        return
    return long_start, long_end


def _filter_matches(
    matcher_output: Iterable[Tuple[int, int, int]], doc: Doc
) -> Iterable[Tuple[Span, Span]]:
    # Filter into two cases:
    # 1. <Short Form> (<Long Form>)
    # 2. <Long Form> (<Short Form>) [this case is most common].
    candidates = []
    for match in matcher_output:
        start = match[1]
        end = match[2]
        # Ignore spans with more than 8 words in.
        if end - start > 8:
            continue
        if end - start > 1:
            # Long form is inside the parens.
            # Take two words before.
            short_form_candidate = doc[start - 2 : start - 1]
            if _short_form_filter(short_form_candidate):
                candidates.append((doc[start:end], short_form_candidate))
        else:
            # Normal case.
            # Short form is inside the parens.
            # Sum character lengths of contents of parens.
            abbreviation_length = sum([len(x) for x in doc[start:end]])
            max_words = min(abbreviation_length + 5, abbreviation_length * 2)
            long_start = max(start - max_words - 1, 0)
            long_end = start
            # Skip whether there is no span
            if long_end <= long_start:
                continue
            # Look up to max_words backwards
            long_form_candidate = doc[long_start:long_end]
            candidates.append((long_form_candidate, doc[start:end]))
    return candidates


def _find_matches_for(
    filtered: Iterable[Tuple[Span, Span]], doc: Doc
) -> Iterable[Tuple[Span, Set[Span]]]:
    matches = []
    seen = {}
    start_seen = {}
    global_matcher = Matcher(doc.vocab)
    for (long_candidate, short_candidate) in filtered:
        abbreviation = find_abbreviation(long_candidate, short_candidate)
        # We look for abbreviations, so...
        if abbreviation is None:
            continue
        global_search = {}
        long_form, short_form = abbreviation
        if short_form.start not in start_seen:
            global_search[short_form] = long_form
        if long_form.start not in start_seen:
            global_search[long_form] = short_form
        # Look for each new abbreviation globally to find lone ones
        for form_seen, form_search in global_search.items():
            start_seen.setdefault(form_seen.start)
            # We've already seen this
            if form_seen.text in seen:
                continue
            seen.setdefault(form_seen.text, form_seen)
            pattern = [{"TEXT": t.text} for t in form_search]
            global_matcher.add(form_seen.text, [pattern])
        matches.append((long_form, short_form))
    # Search for lone abbreviations globally
    for key, start, end in global_matcher(doc):
        # We've already found this match
        if start in start_seen:
            continue
        text = doc.vocab.strings[key]
        # Never seen, skip
        if text not in seen:
            continue
        already_seen = seen[text]
        global_match = Span(doc, start, end)
        start_seen.setdefault(global_match.start)
        seen.setdefault(global_match.text, global_match)
        # Short form should be the shortest
        if len(already_seen) < len(global_match):
            short_form = already_seen
            long_form = global_match
        else:
            short_form = global_match
            long_form = already_seen
        matches.append((long_form, short_form))
    yield from sorted(matches, key=lambda x: x[0].start)


def _short_form_filter(span: Span) -> bool:
    # All words are between length 2 and 10
    if not all([2 <= len(x) < 10 for x in span]):
        return False
    # At least one word is alpha numeric
    if not any([x.is_alpha for x in span]):
        return False
    return True
