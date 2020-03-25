from collections import defaultdict
from typing import Dict, List, Optional, Set, Tuple, Union

from spacy.matcher import Matcher
from spacy.tokens import Doc, Span

from .util import span_idx2i


class AbbreviationDetector:
    """
    Detects abbreviations which are acronyms or by using the algorithm in 
    "A simple algorithm for identifying abbreviation definitions in biomedical 
    text.", (Schwartz & Hearst, 2003).

    This class sets the `._.abbreviations` attribute on spaCy Doc.

    The abbreviations attribute is a `List[Span]` where each Span has the `Span._.long_form`
    attribute set to the long form definition of the abbreviation.

    Note that this class does not replace the spans, or merge them.
    """

    def __init__(self, nlp) -> None:
        Doc.set_extension("abbreviations", default=[], force=True)
        Span.set_extension("long_form", default=None, force=True)

        self.matcher = Matcher(nlp.vocab)
        self.matcher.add(
            "abbreviations",
            [
                # Pattern for abbreviations not enclosed in brackets
                [{"IS_ALPHA": True, "IS_UPPER": True, "LENGTH": {">": 1}},],
                # Pattern for abbreviations enclosed in brackets
                [
                    {"TEXT": {"IN": ["(", "["]}},
                    {"IS_ALPHA": True, "LENGTH": {">": 1}},
                    {"TEXT": {"IN": [")", "]"]}},
                ],
            ],
        )

        self.global_matcher = Matcher(nlp.vocab)

    def find(self, span: Span, doc: Doc) -> Tuple[Span, Set[Span]]:
        """
        Functional version of calling the matcher for a single span.
        This method is helpful if you already have an abbreviation which
        you want to find a definition for.
        """
        dummy_matches = [(-1, int(span.start), int(span.end))]
        filtered = _filter_matches(dummy_matches, doc)
        abbreviations = self.find_matches_for(filtered, doc)

        if not abbreviations:
            return span, set()
        else:
            return abbreviations[0]

    def __call__(self, doc: Doc) -> Doc:
        matches = self.matcher(doc)
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
        occurences = self.find_matches_for(filtered, doc)

        for (long_form, short_forms) in occurences:
            for short in short_forms:
                short._.long_form = long_form
                doc._.abbreviations.append(short)
        return doc

    def find_matches_for(
        self, filtered: List[Tuple[Span, Span]], doc: Doc
    ) -> List[Tuple[Span, Set[Span]]]:
        rules = {}
        all_occurences: Dict[Span, Set[Span]] = defaultdict(set)
        already_seen_long: Set[str] = set()
        already_seen_short: Set[str] = set()
        for (long_candidate, short_candidate) in filtered:
            short, long = find_abbreviation(long_candidate, short_candidate)
            # We need the long and short form definitions to be unique, because we need
            # to store them so we can look them up later. This is a bit of a
            # pathalogical case also, as it would mean an abbreviation had been
            # defined twice in a document. There's not much we can do about this,
            # but at least the case which is discarded will be picked up below by
            # the global matcher. So it's likely that things will work out ok most of the time.
            new_long = (
                True  # long.string not in already_seen_long if long else False
            )
            new_short = True  # short.string not in already_seen_short
            if long is not None and new_long and new_short:
                already_seen_long.add(long.string)
                already_seen_short.add(short.string)
                all_occurences[long].add(short)
                rules[long.string] = long
                # Add a rule to a matcher to find exactly this substring.
                self.global_matcher.add(
                    long.string, None, [{"ORTH": x.text} for x in short]
                )
        to_remove = set()
        global_matches = self.global_matcher(doc)
        for match, start, end in global_matches:
            string_key = self.global_matcher.vocab.strings[match]
            to_remove.add(string_key)
            all_occurences[rules[string_key]].add(doc[start:end])
        for key in to_remove:
            # Clean up the global matcher.
            self.global_matcher.remove(key)

        return list((k, v) for k, v in all_occurences.items())


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
    long_form = " ".join([x.text for x in long_form_candidate])
    short_form = " ".join([x.text for x in short_form_candidate])

    long_index = len(long_form) - 1
    short_index = len(short_form) - 1

    bounds_idx = _find_abbreviation(
        long_form=long_form,
        long_index=long_index,
        short_form=short_form,
        short_index=short_index,
    )

    if not bounds_idx:
        return short_form_candidate, None

    start_idx, end_idx = bounds_idx
    start, end = span_idx2i(long_form_candidate, start_idx, end_idx)

    return (
        short_form_candidate,
        long_form_candidate[start:end],
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
    while short_index >= 0 and long_index >= 0:
        # Get next abbreviation char to check
        short_char = short_form[short_index].lower()
        # Don't check non alphabetic characters
        if not short_char.isalpha():
            short_index -= 1
            continue
        long_char = long_form[long_index].lower()
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
        if long_index == 0:
            long_index -= 1
            short_index -= 1
        elif long_index > 0:
            long_index -= 1
            short_index -= 1
            if not is_starting_char:
                has_internal_match = True
    if short_index >= 0:
        return
    return max(long_index, 0), long_index_end + 1


def _filter_matches(
    matcher_output: List[Tuple[int, int, int]], doc: Doc
) -> List[Tuple[Span, Span]]:
    # Filter into two cases:
    # 1. <Short Form> ( <Long Form> )
    # 2. <Long Form> (<Short Form>) [this case is most common].
    candidates = []
    for match in matcher_output:
        start = match[1]
        end = match[2]
        # Ignore spans with more than 8 words in.
        if end - start > 8:
            continue
        if end - start > 3:
            # Long form is inside the parens.
            # Take two words before.
            short_form_candidate = doc[start - 3 : start - 1]
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


def _short_form_filter(span: Span) -> bool:
    # All words are between length 2 and 10
    if not all([2 < len(x) < 10 for x in span]):
        return False
    # At least one word is alpha numeric
    if not any([x.is_alpha for x in span]):
        return False
    return True
