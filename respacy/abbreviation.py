from collections import defaultdict
from typing import Dict, List, Optional, Set, Tuple, Union

from spacy.lang import char_classes
from spacy.matcher import Matcher
from spacy.tokens import Doc, Span


def find_abbreviation_mwo(
    *, long_form: str, long_index: int, short_form: str, short_index: int
) -> Union[Tuple[int, int], None]:
    """
    Find an abbreviation matching in multiword only.
    Implements an abbreviation detection algorithm which works by enumerating the characters 
    in the short form of the abbreviation, checking that they can be matched against characters 
    in a candidate text for the long form in order, as well as requiring that each letter of 
    the abbreviated form matches the _beginning_ letter of a word.

    Parameters
    ----------
    long_form: str, required.
        The long form candidate of the definition.
    long_index: int, required.
        The last character index of the long form candidate.
    short_form: str, required.
        The abbreviation candidate.
    short_index: int, required.
        The last character index of the abbreviation candidate.

    Returns
    -------
    The first and last character index of the long form expansion, or None is a match is not found.
    """

    # Hold as bound delimiter
    long_index_end = long_index

    while short_index >= 0 and long_index >= 0:

        # Get next abbreviation char to check
        current_char = short_form[short_index].lower()

        # We don't check non alphabetic characters.
        # NOTE: should never happen a non alphabetic char here.
        if not current_char.isalpha():
            short_index -= 1
            continue

        # Jump to the beginning of a word
        # (first non alpha-numeric char or left ending of the string)
        while long_index >= 0 and long_form[long_index].isalnum():
            long_index -= 1

        # Non alpha-numeric tail char, skip
        if long_index == long_index_end:
            long_index -= 1
            long_index_end -= 1
            continue

        # An abbreviation char has matched
        # move to the next one
        if long_form[long_index + 1].lower() == current_char:
            short_index -= 1

        # Go forward
        long_index -= 1

    if short_index >= 0:
        return

    return long_index, long_index_end


def find_abbreviation_swf(
    *, long_form: str, long_index: int, short_form: str, short_index: int
) -> Union[Tuple[int, int], None]:
    """
    Find an abbreviation matching within a single word first.
    Implements the abbreviation detection algorithm in "A simple algorithm
    for identifying abbreviation definitions in biomedical text.", (Schwartz & Hearst, 2003).

    The algorithm works by enumerating the characters in the short form of the abbreviation,
    checking that they can be matched against characters in a candidate text for the long form
    in order, as well as requiring that the first letter of the abbreviated form matches the
    _beginning_ letter of a word.

    Parameters
    ----------
    long_form: str, required.
        The long form candidate of the definition.
    long_index: int, required.
        The last character index of the long form candidate.
    short_form: str, required.
        The abbreviation candidate.
    short_index: int, required.
        The last character index of the abbreviation candidate.

    Returns
    -------
    The first and last character index of the long form expansion, or None is a match is not found.
    """

    # Hold as bound delimiter
    long_index_end = long_index

    while short_index >= 0:

        # Get next abbreviation char to check
        current_char = short_form[short_index].lower()

        # We don't check non alpha-numeric characters.
        # NOTE: should never happen a non alphabetic char here.
        if not current_char.isalpha():
            short_index -= 1
            continue

        # Does the character match at this position? ...
        while (
            (long_index >= 0 and long_form[long_index].lower() != current_char)
            or
            # ... or if we are checking the first character of the abbreviation, we enforce
            # to be the _starting_ character of a span.
            (
                short_index == 0
                and long_index > 0
                and long_form[long_index - 1].isalnum()
            )
        ):
            if (
                not long_form[long_index].isalnum()
                and long_index == long_index_end
            ):
                long_index_end -= 1

            long_index -= 1

        if long_index < 0:
            return

        long_index -= 1
        short_index -= 1

    return long_index


def find_abbreviation(
    long_form_candidate: Span, short_form_candidate: Span
) -> Tuple[Span, Optional[Span]]:
    """
    Implements the abbreviation detection algorithm in "A simple algorithm
    for identifying abbreviation definitions in biomedical text.", (Schwartz & Hearst, 2003).

    The algorithm works by enumerating the characters in the short form of the abbreviation,
    checking that they can be matched against characters in a candidate text for the long form
    in order, as well as requiring that the first letter of the abbreviated form matches the
    _beginning_ letter of a word.

    Parameters
    ----------
    long_form_candidate: Span, required.
        The spaCy span for the long form candidate of the definition.
    short_form_candidate: Span, required.
        The spaCy span for the abbreviation candidate.

    Returns
    -------
    A Tuple[Span, Optional[Span]], representing the short form abbreviation and the
    span corresponding to the long form expansion, or None if a match is not found.
    """
    long_form = " ".join([x.text for x in long_form_candidate])
    short_form = " ".join([x.text for x in short_form_candidate])

    long_index = len(long_form) - 1
    short_index = len(short_form) - 1

    # Check multiword first as preferred detection
    long_bounds = find_abbreviation_mwo(
        long_form=long_form,
        long_index=long_index,
        short_form=short_form,
        short_index=short_index,
    )

    # If multiword detection failed, try singleword one
    if long_bounds is None:
        long_bounds = find_abbreviation_swf(
            long_form=long_form,
            long_index=long_index,
            short_form=short_form,
            short_index=short_index,
        )

    # If all failed, return empty
    if long_bounds is None:
        return short_form_candidate, None

    #
    if isinstance(long_bounds, int):
        long_i_start = long_i_end = long_bounds
    else:
        long_i_start, long_i_end = long_bounds

    # If we complete the string, we end up with lower 0 here,
    # but really we want all of the text.
    long_i_start = max(long_i_start, 0)

    # Now we know the character index of the start and the end of the character span,
    # here we just translate them to the first token beginning after that
    # start and the last before that end, so we can return a spaCy span instead.
    word_lengths = 0
    starting_index = None
    ending_index = None
    for i, word in enumerate(long_form_candidate):
        word_lengths += len(word)
        if word_lengths > long_i_start and starting_index is None:
            starting_index = i
        if word_lengths >= long_i_end:
            ending_index = i
            break

    # Increment ending_index whether
    # it is matching a single word
    if ending_index == starting_index:
        ending_index += 1

    return (
        short_form_candidate,
        long_form_candidate[starting_index:ending_index],
    )


def filter_matches(
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
            if short_form_filter(short_form_candidate):
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


def short_form_filter(span: Span) -> bool:
    # All words are between length 2 and 10
    if not all([2 < len(x) < 10 for x in span]):
        return False
    # At least one word is alpha numeric
    if not any([x.is_alpha for x in span]):
        return False
    return True


class AbbreviationDetector:
    """
    Detects abbreviations using the algorithm in "A simple algorithm for identifying
    abbreviation definitions in biomedical text.", (Schwartz & Hearst, 2003).

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
                [{"IS_ALPHA": True, "IS_UPPER": True, "LENGTH": {">": 1}},],
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
        filtered = filter_matches(dummy_matches, doc)
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
                    x[1] + (1 if doc[x[1]].text in char_classes.PUNCT else 0),
                    x[2]
                    - (1 if doc[x[2] - 1].text in char_classes.PUNCT else 0),
                )
                for x in matches
            ]
        )
        filtered = filter_matches(matches_no_punct, doc)
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
            new_long = long.string not in already_seen_long if long else False
            new_short = short.string not in already_seen_short
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
