from typing import Union

import regex as re
from spacy.attrs import DEP, LEMMA, POS, TAG, intify_attr
from spacy.errors import Errors, MatchPatternError
from spacy.tokens import Doc, Span, Token

from ..defaults import spacy_version

if spacy_version < 3:
    from spacy.util import get_json_validator, validate_json

    from ._schemas import TOKEN_PATTERN_SCHEMA
else:
    # Pattern validation changed as of spaCy 3.0
    from spacy.attrs import MORPH  # type: ignore
    from spacy.schemas import validate_token_pattern  # type: ignore

from functools import partial

from ._schemas import TOKEN_PATTERN_SCHEMA

__all__ = ["Matcher"]

DocLike = Union[Doc, Span]


class Matcher(object):
    def __init__(self, vocab, validate=False):

        self._specs = {}
        self._patterns = {}
        self._callbacks = {}
        self._seen_attrs = set()
        self.vocab = vocab
        self.validate = validate

        try:
            self._validator = partial(
                validate_json,
                validator=get_json_validator(TOKEN_PATTERN_SCHEMA),
            )
        except NameError:
            self._validator = validate_token_pattern

    def __len__(self):
        """
        Get the number of rules added to the matcher.
        Note that this only returns the number of rules (identical with the number of IDs),
        not the number of individual patterns.

        Returns
        ------
        int
            The number of rules.
        """
        return len(self._patterns)

    def __contains__(self, key: str):
        """
        Check whether the matcher contains rules for a key.

        Parameters
        ----------
        key: str
            The key.

        Returns
        -------
        bool
            Whether the matcher contains rules for this key.
        """
        key = self._normalize_key(key)
        return key in self._patterns

    def __getitem__(self, key: str):
        """
        Retrieve the pattern stored for a key.
        A KeyError is raised if the key does not exist.

        Parameters
        ----------
        key: str
            The key to retrieve.

        Returns
        -------
        tuple
            The rule, as an (on_match, patterns) tuple.
        """
        key = self._normalize_key(key)
        return (self._callbacks[key], self._patterns[key])

    def get(self, key: str, default=None):
        """
        Retrieve the pattern stored for a key,
        or default if it does not exist.

        Parameters
        ----------
        key: str
            The key to retrieve.

        Returns
        -------
        tuple:
            The rule, as an (on_match, patterns) tuple.
        """
        key = self._normalize_key(key)
        return self[key] if key in self else (default, default)

    def add(self, key, patterns, on_match=None):
        """
        Add a match-rule to the matcher.
        A match-rule consists of:
            an ID key,
            a list of patterns,
            an on_match callback.
        If the key exists, the patterns are appended to the
        previous ones, and the previous on_match callback is replaced. The
        `on_match` callback will receive the arguments `(matcher, doc, i, matches)`.
        You can also set `on_match` to `None` to not perform any action.
        A pattern consists of one or more `token_specs`, where a `token_spec`
        is a dictionary mapping attribute IDs to values, and optionally a
        quantifier operator under the key "op". The available quantifiers are:
        '!': Negate the pattern, by requiring it to match exactly 0 times.
        '?': Make the pattern optional, by allowing it to match 0 or 1 times.
        '+': Require the pattern to match 1 or more times.
        '*': Allow the pattern to zero or more times.
        The + and * operators are usually interpretted "greedily", i.e. longer
        matches are returned where possible. However, if you specify two '+'
        and '*' patterns in a row and their matches overlap, the first
        operator will behave non-greedily. This quirk in the semantics makes
        the matcher more efficient, by avoiding the need for back-tracking.

        Parameters
        ----------
        key: str
            The match ID.
        patterns: list
            The patterns to add for the given key.
        on_match: callable
            Optional callback executed on match.
        """
        errors = {}
        if on_match is not None and not hasattr(on_match, "__call__"):
            raise ValueError(Errors.E171.format(arg_type=type(on_match)))
        for i, pattern in enumerate(patterns):
            if len(pattern) == 0:
                raise ValueError(Errors.E012.format(key=key))
            if not isinstance(pattern, list):
                raise ValueError(Errors.E178.format(pat=pattern, key=key))
            if self.validate:
                errors[i] = self._validator(pattern)
        if any(err for err in errors.values()):
            raise MatchPatternError(key, errors)
        key = self._normalize_key(key)
        self._specs.setdefault(key, [])
        for i, pattern in enumerate(patterns):
            try:
                patternspec = _preprocess_pattern(pattern)
            except ValueError as err:
                raise MatchPatternError(key, {i: [str(err)]})
            self._specs[key].append(patternspec)
            for token in pattern:
                for attr in token:
                    iattr = intify_attr(attr)
                    self._seen_attrs.add(iattr)
        self._patterns.setdefault(key, [])
        self._callbacks[key] = on_match
        self._patterns[key].extend(patterns)

    def remove(self, key: str):
        """
        Remove a rule from the matcher.
        A ValueError is raised if the key does not exist.

        Parameters
        ----------
        key: str
            The ID of the match rule.
        """
        key = self._normalize_key(key)
        if key not in self._patterns:
            raise ValueError(Errors.E175.format(key=key))
        self._specs.pop(key)
        self._patterns.pop(key)
        self._callbacks.pop(key)

    def __call__(self, doclike: DocLike, allow_missing=False):
        """
        Find all token sequences matching the supplied patterns.

        Parameters
        ----------
        doc: Doc
            The document to match over.

        Returns
        -------
        list
            A list of `(match_id, start, end)` tuples,
            describing the matches. A match tuple describes a span
            `doc[start:end]`.
        """
        if not allow_missing:
            # legacy between spaCy versions
            attr2pipe = {
                TAG: ("tagger", "is_tagged"),
                POS: ("morphologizer", "is_tagged"),
                LEMMA: ("lemmatizer", "is_tagged"),
                DEP: ("parser", "is_parsed"),
            }
            if spacy_version >= 3:
                attr2pipe[MORPH] = ("morphologizer", None)
            for attr, (pipe, flag) in attr2pipe.items():
                if (
                    attr not in self._seen_attrs
                    or (spacy_version >= 3 and doclike.has_annotation(attr))
                    or (spacy_version < 3 and getattr(doclike, flag))
                ):
                    continue
                raise ValueError(
                    Errors.E155.format(
                        pipe=pipe, attr=self.vocab.strings.as_string(attr)
                    )
                )
        matches = []
        seen = set()
        for match in _find_matches(doclike, self._specs):
            if match in seen:
                continue
            seen.add(match)
            matches.append(match)
        for i, match in enumerate(matches):
            on_match = self._callbacks.get(match[0], None)
            if on_match is not None:
                on_match(self, doclike, i, matches)
        return matches

    def _normalize_key(self, key):
        if isinstance(key, int):
            return key
        return (
            self.vocab.strings.add(key)
            if key not in self.vocab.strings
            else self.vocab.strings[key]
        )


def _find_matches(tokens, specs):
    attrs_maps_cache = {}
    num_tokens = len(tokens)
    for key, pattern_specs in specs.items():
        for pattern_spec, anchor_gs in pattern_specs:
            candidates = [((0, num_tokens), {})]
            for attr, (xp, is_ext) in pattern_spec.items():
                if attr not in attrs_maps_cache:
                    attrs_maps_cache[attr] = _attr_maps(attr, tokens, is_ext)
                i2idx, idx2i, text = attrs_maps_cache[attr]
                maxlen = len(text)
                new_candidates = []
                for candidate, anchor_ss in candidates:
                    start_idx = i2idx[candidate[0]]
                    end_idx = i2idx[candidate[1]]
                    curr_text = text[start_idx:end_idx]
                    for match in xp.finditer(curr_text, overlapped=True):
                        span = (
                            start_idx + match.span()[0],
                            start_idx + match.span()[1],
                        )
                        start, end = _span_idx2i(span, idx2i, maxlen)
                        new_ss = {}
                        for i in range(len(match.groups())):
                            group_i = i + 1
                            if group_i not in anchor_gs:
                                continue
                            span_g = match.span(group_i)
                            span = (
                                start_idx + span_g[0],
                                start_idx + span_g[1],
                            )
                            new_ss[group_i] = _span_idx2i(span, idx2i, maxlen)
                        if anchor_ss:
                            should_stop = False
                            for group_i, span in new_ss.items():
                                if anchor_ss[group_i] != span:
                                    should_stop = True
                                    break
                            if should_stop:
                                continue
                        new_candidates.append(((start, end), new_ss))
                candidates = new_candidates
            matches = [c[0] for c in candidates]
            yield from (
                (key, *match) for match in _filter_out_submatches(matches)
            )


def _attr_maps(attr, tokens, is_extension):
    i2idx = {}
    idx2i = {}
    text_tokens = []
    curr_length = 0
    num_spaces = 0
    regex_attr = attr == "REGEX"
    for i, token in enumerate(tokens):
        pad = i if not regex_attr else num_spaces
        idx = curr_length + pad
        i2idx[i] = idx
        idx2i[idx] = i
        if is_extension:
            value = token._.get(attr)
        else:
            value = _get_token_attr(token, attr)
        value = str(value)
        curr_length += len(value)
        if regex_attr:
            value += token.whitespace_
            num_spaces += len(token.whitespace_)
        else:
            num_spaces = i
        text_tokens.append(value)
    curr_length += num_spaces
    i2idx[len(tokens)] = curr_length
    idx2i[curr_length] = len(tokens)
    text = ("" if regex_attr else " ").join(text_tokens)
    return (i2idx, idx2i, text)


def _span_idx2i(span_idx, idx2i, maxlen):
    start = span_idx[0]
    while start not in idx2i and start < maxlen:
        start += 1
    end = span_idx[1]
    while end not in idx2i and end < maxlen:
        end += 1
    return idx2i[start], idx2i[end]


def _filter_out_submatches(matches):
    i1 = 0
    num_matches = len(matches)
    while i1 < num_matches:
        yield matches[i1]
        i2 = i1 + 1
        while (
            i2 < num_matches
            and matches[i1][0] < matches[i2][0]
            and matches[i1][1] == matches[i2][1]
        ):
            i2 += 1
        i1 = i2


def _preprocess_pattern(pattern):
    pattern_spec = {}
    num_tokens = len(pattern)
    for tokens_spec in pattern:
        if not isinstance(tokens_spec, dict):
            raise ValueError(Errors.E154.format())
        for attr, value in {**tokens_spec}.items():
            if not (
                isinstance(value, str)
                or isinstance(value, bool)
                or isinstance(value, int)
                or isinstance(value, dict)
            ):
                raise ValueError(
                    Errors.E153.format(vtype=type(value).__name__)
                )
            # normalize attributes
            if attr.islower():
                del tokens_spec[attr]
                attr = attr.upper()
                tokens_spec[attr] = value
            if attr == "SENT_START":
                del tokens_spec[attr]
                attr = "IS_SENT_START"
                tokens_spec[attr] = value
            elif attr == "OP":
                continue
            is_extension = attr == "_"
            if is_extension and not isinstance(value, dict):
                raise ValueError(Errors.E154.format())
            if not is_extension and isinstance(value, dict):
                for k, v in {**value}.items():
                    if k.isalpha() and k.isupper():
                        continue
                    del value[k]
                    value[k.upper()] = v
            for a in value.keys() if is_extension else [attr]:
                pattern_spec.setdefault(a, ([None] * num_tokens, is_extension))
    for i, tokens_spec in enumerate(pattern):
        _align_tokens_spec(pattern_spec, tokens_spec, i)
    return _finalize_pattern_spec(pattern_spec)


# Quantifiers
_NONE = "x"
_ONE = "1"
_ONE_PLUS = "+"
_ZERO = "!"
_ZERO_ONE = "?"
_ZERO_PLUS = "*"

# Regex
_XP_ONE_TOKEN = r"[^\s]+"
_XP_TOKEN_START = r"(?:\s|^)"
_XP_TOKEN_DELIM = r"(?:\s|^|$)"

# Predicates
_REGEX_PREDICATES = ("REGEX",)
_SETMEMBER_PREDICATES = ("IN", "NOT_IN")
_COMPARISON_PREDICATES = ("==", "!=", ">=", "<=", ">", "<")

# Other
_ANCHOR_QS = (_ONE, _ONE_PLUS)


def _finalize_pattern_spec(spec):
    anchor_gs = set()
    final_spec = {}
    for attr, (xps, is_extension) in spec.items():
        if not anchor_gs:
            for i, (_, q) in enumerate(xps):
                if q not in _ANCHOR_QS:
                    continue
                anchor_gs.add(i + 1)
        if attr in _REGEX_PREDICATES:
            regex = "".join([x[0] for x in xps])
        else:
            regex = "".join([_XP_TOKEN_START, *(x[0] for x in xps)])
        flags = re.U | re.M
        if attr in ("LENGTH", "LOWER"):
            flags |= re.I
        final_spec[attr] = (re.compile(regex, flags=flags), is_extension)
    sort_by = lambda x: x[0] not in ("LEMMA", "LOWER", "TEXT")
    final_spec = {k: v for k, v in sorted(final_spec.items(), key=sort_by)}
    return (final_spec, anchor_gs)


def _align_tokens_spec(spec, tokens_spec, index):
    xp_cond_delim = f"(?({index + 1}){_XP_TOKEN_DELIM}|)"
    for a1, (xp, q) in _attrs_spec_from_tokens_spec(tokens_spec):
        fix_q = q if q != _ZERO else _ONE
        needs_delim = fix_q == _ONE
        for a2, (xps, _) in spec.items():
            _q = _xp = None
            if not a1 or a1 == a2:
                _q = q
                _xp = xp
            elif xps[index] == None:
                _q = fix_q
                _xp = _XP_ONE_TOKEN
            if not (_q and _xp):
                continue
            lazy = _q == _ONE_PLUS and _xp == _XP_ONE_TOKEN
            _xp = _re_wrap_quantifier(_q, _xp, lazy)
            if needs_delim:
                _xp += xp_cond_delim
            xps[index] = (_xp, _q)


def _attrs_spec_from_tokens_spec(tokens_spec):
    if not tokens_spec:
        yield None, (_XP_ONE_TOKEN, _ONE)
    elif "REGEX" in tokens_spec:
        yield "REGEX", (tokens_spec["REGEX"], _NONE)
    else:
        q = tokens_spec.get("OP")
        if q and len(tokens_spec) == 1:
            yield None, (_XP_ONE_TOKEN, q)
        else:
            if not q:
                q = _ONE  # default quantifier
            for (attr, xp) in _attrs_xp_from_tokens_spec(tokens_spec):
                yield attr, (xp, q)


def _attrs_xp_from_tokens_spec(tokens_spec, skip_validate=False):
    for attr, value in tokens_spec.items():
        if attr == "OP":
            continue
        if attr == "_":
            yield from _attrs_xp_from_tokens_spec(value, True)
            continue
        if (
            not skip_validate
            and attr not in TOKEN_PATTERN_SCHEMA["items"]["properties"]
        ):
            raise ValueError(Errors.E152.format(attr=attr))
        if isinstance(value, int):
            value = str(value)
        if isinstance(value, dict):
            for p, a in value.items():
                if p in _REGEX_PREDICATES:
                    yield attr, _xp_from_regex(a)
                elif p in _SETMEMBER_PREDICATES:
                    yield attr, _xp_from_setmember(p, a)
                elif p in _COMPARISON_PREDICATES:
                    yield attr, _xp_from_comparison(p, a)
                else:
                    raise ValueError()
            continue
        yield attr, (
            re.escape(value) if attr not in _REGEX_PREDICATES else value
        )


def _xp_from_regex(regex):
    # Symbols `^` and `$` for start, end string must be removed
    # Here we don't use `re.sub` because works bad with raw strings
    split = re.split(r"(?:(?<!\[|\\)\^|(?<!\\)\$)", regex)
    merge = "".join(split)
    return merge if len(split) > 1 else "".join([r"[^ ]*?", merge, r"[^ ]*?"])


def _xp_from_setmember(operator, args):
    # We optimize in case of a unique argument
    if len(args) == 1:
        pipe = re.escape(args[0])
    else:
        terms = (re.escape(term) for term in args)
        pipe = "".join([r"(?:", r"|".join(terms), r")"])
    return f"(?!{pipe})[^ ]+" if operator == "NOT_IN" else pipe


def _xp_from_comparison(operator, length):
    return _re_wrap_length(operator, length)


_WRAP_Q_LOOKUP = {
    _NONE: "({xp})",
    _ONE: "({xp})",
    _ONE_PLUS: "((?:{{xp}}{delim})+)".format(delim=_XP_TOKEN_DELIM),
    _ZERO: "(?!{xp})([^ ]+)",
    _ZERO_ONE: "({{xp}}{delim})?".format(delim=_XP_TOKEN_DELIM),
    _ZERO_PLUS: "((?:{{xp}}{delim})*)".format(delim=_XP_TOKEN_DELIM),
}


def _re_wrap_quantifier(q, xp, lazy=False):
    if q is None:
        return xp
    if lazy and q not in (_ONE_PLUS, _ZERO_PLUS):
        raise ValueError
    if q not in _WRAP_Q_LOOKUP:
        keys = ", ".join(_WRAP_Q_LOOKUP.keys())
        raise ValueError(Errors.E011.format(op=q, opts=keys))
    xpq = _WRAP_Q_LOOKUP[q].format(xp=xp)
    if not lazy:
        return xpq
    return "".join([xpq[:-1], "?", xpq[-1:]])


def _re_wrap_length(cmp, l):
    if cmp == "==":
        return "(?:[^ ]{{{}}}+)".format(l)
    elif cmp == "!=":
        return "(?:[^ ]{{1,{}}}+|[^ ]{{{},}}+)".format(l - 1, l + 1)
    elif cmp == ">=":
        return "(?:[^ ]{{{},}}+)".format(l)
    elif cmp == "<=":
        return "(?:[^ ]{{1,{}}}+)".format(l)
    elif cmp == ">":
        return "(?:[^ ]{{{},}}+)".format(l + 1)
    elif cmp == "<":
        return "(?:[^ ]{{1,{}}}+)".format(l - 1)
    else:
        raise ValueError(
            Errors.E126.format(bad=cmp, good=_COMPARISON_PREDICATES)
        )


def _get_token_attr(token: Token, attr: str):
    if attr == "REGEX":
        return token.text
    elif attr == "LEMMA":
        return token.lemma_.lower()
    elif attr == "NORM":
        if not token.norm_:
            return token.lex.norm
        return token.norm_
    elif attr == "POS":
        return token.pos_
    elif attr == "TAG":
        return token.tag_
    elif attr == "DEP":
        return token.dep_
    elif attr == "SENT_START":
        return token.sent_start
    elif attr == "ENT_TYPE":
        return token.ent_type_
    elif attr == "ORTH":
        return token.orth_
    elif attr == "TEXT":
        return token.text
    elif attr == "LOWER":
        return token.lower_
    elif attr == "SHAPE":
        return token.shape_
    elif attr == "PREFIX":
        return token.prefix_
    elif attr == "SUFFIX":
        return token.suffix_
    # LENGTH attribute must be checked on text
    # and it cannot live together with
    # another textual attribute, so we set it
    # as LOWER for a performance reason
    elif attr == "LENGTH":
        return token.lower_
    elif attr == "CLUSTER":
        return token.cluster
    elif attr == "LANG":
        return token.lang_
    elif token.check_flag(intify_attr(attr)):
        return "True"
    return "False"
