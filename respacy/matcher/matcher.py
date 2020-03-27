from functools import lru_cache

import regex as re
from spacy.attrs import DEP, LEMMA, POS, TAG, intify_attr
from spacy.errors import Errors, MatchPatternError
from spacy.matcher import Matcher as _Matcher
from spacy.tokens.doc import Doc
from spacy.tokens.token import Token
from spacy.util import get_json_validator, validate_json
from srsly import json_dumps

from ..util import span_idx2i
from ._schemas import TOKEN_PATTERN_SCHEMA

__all__ = ["Matcher"]


class Matcher(object):
    def __init__(self, vocab, validate=False):

        self._specs = {}
        self._patterns = {}
        self._callbacks = {}
        self._seen_attrs = set()
        self.vocab = vocab

        self.validator = (
            get_json_validator(TOKEN_PATTERN_SCHEMA) if validate else None
        )

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
        Retrieve the pattern stored for a key.

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
        return self[key] if key in self else default

    def add(self, key: str, patterns, on_match=None):
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
        on_match: callable, optional
             , by default None.
        """
        errors = {}
        if on_match is not None and not hasattr(on_match, "__call__"):
            raise ValueError(Errors.E171.format(arg_type=type(on_match)))
        for i, pattern in enumerate(patterns):
            if len(pattern) == 0:
                raise ValueError(Errors.E012.format(key=key))
            if not isinstance(pattern, list):
                raise ValueError(Errors.E178.format(pat=pattern, key=key))
            if self.validator:
                errors[i] = validate_json(pattern, self.validator)
        if any(err for err in errors.values()):
            raise MatchPatternError(key, errors)

        key = self._normalize_key(key)

        self._specs.setdefault(key, [])
        for pattern in patterns:
            spec = _preprocess_pattern(pattern)
            self._specs[key].append(spec)
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

    def __call__(self, doc: Doc, best_sort: bool = False):
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
        if (
            len(set((LEMMA, POS, TAG)) & self._seen_attrs) > 0
            and not doc.is_tagged
        ):
            raise ValueError(Errors.E155.format())

        if DEP in self._seen_attrs and not doc.is_parsed:
            raise ValueError(Errors.E156.format())

        cache = {}
        coordicatch = {}
        matches = []
        matcher = _Matcher(self.vocab)
        tokens = [token for token in doc]
        doclen = len(tokens)

        for key, i, start, end in _find_re_matches(tokens, self._specs):
            # starts = coordicatch.setdefault(start, {})
            # ends = starts.setdefault(end, [])
            # ends.append((key, catcher, {}))

            # keys = ends.setdefault(key, [])
            # keys.append((catcher, {}))

            candidate = tokens[start:end]
            if doclen == len(candidate):
                matcher.add(key, [self._patterns[key][i]])
                continue
            catcher = self._specs[key][i][0]
            for s, e in _find_matches(tokens[start:end], catcher, cache):
                matches.append((key, start + s, start + e))

            # catcher = self._specs[key][i][0]
            # for s, e in catcher(candidate):
            #     matches.append((norm_key, start + s, start + e))

        for key, start, end in matcher(doc):
            matches.append((key, start, end))

        # matches = [match for match in _find_matches(tokens, coordicatch)]

        if best_sort:
            matches.sort(key=lambda x: (x[1], -x[2], x[0]))

        for i, match in enumerate(matches):
            on_match = self._callbacks.get(match[0], None)
            if on_match is not None:
                on_match(self, doc, i, matches)

        return matches

    def _normalize_key(self, key):
        if isinstance(key, int):
            return key
        return (
            self.vocab.strings.add(key)
            if key not in self.vocab.strings
            else self.vocab.strings[key]
        )


def _find_re_matches(tokens, specs):
    text = "".join([t.text_with_ws for t in tokens])
    maxdlen = len(tokens)
    maxtlen = len(text)
    for key, values in specs.items():
        for i, spec in enumerate(values):
            if not spec[1]:
                yield (key, i, 0, maxdlen)
                continue
            for match in spec[1].finditer(text, concurrent=True):
                start, end = span_idx2i(
                    tokens, match.start(), match.end(), maxtlen
                )
                # print(spec[1], text[match.start(): match.end()], tokens[start: end])
                if start == end:
                    continue
                # if not spec[2]:
                #     yield (key, i, start, end)
                # candidate = tokens[start:end]
                # lemmas = " ".join([t.lemma_ for t in candidate])
                # maxllen = len(lemmas)
                # for match in spec[2].finditer(lemmas):
                #     gap = lemmas[:match.start()].count(" ")
                #     s = gap + 1
                #     e = gap + lemmas[match.start(): match.end()].count(" ")
                #     # s, e = span_idx2i(
                #     #     candidate, match.start(), match.end(), maxllen
                #     # )
                #     print(spec[2], lemmas[match.start(): match.end()], candidate[s: e])
                #     if s == e:
                #         continue
                #     yield (key, i, start + s, start + e)
                if not spec[2] or spec[2].search(
                    " ".join([t.lemma_ for t in tokens[start:end]])
                ):
                    yield (key, i, start, end)


def _find_matches(tokens, coordicatch):
    cache = {}
    active_catchers = {}
    for i, token in enumerate(tokens):
        if i in coordicatch:
            active_catchers.update(coordicatch[i])
        if i in active_catchers:
            del active_catchers[i]
        if not active_catchers:
            continue
        for catchers in active_catchers.values():
            for key, catcher, catchings in catchers:
                yield from (
                    (key, start, end)
                    for start, end in _catch_in_token(
                        token, i, catcher, catchings, cache
                    )
                )


def _find_matches(tokens, catcher, cache):
    catchings = {}
    for i, token in enumerate(tokens):
        yield from _catch_in_token(token, i, catcher, catchings, cache)


ONE = "1"
ONE_PLUS = "+"
ZERO = "!"
ZERO_ONE = "?"
ZERO_PLUS = "*"


def _catch_in_token(token, i, catcher, catchings, cache):
    c = 0
    new_catchings = {}
    items = catcher[0]
    head_end = catcher[1]
    tail_start = catcher[2]
    maxclen = len(items) - 1
    for c in range(len(items)):
        # if head ended
        # check already open catchings only
        if c > head_end and c not in catchings:
            continue
        op, cf = items[c]
        catch = {}
        if c in catchings:
            catch = catchings[c]
            del catchings[c]
        if not cf(token, cache):
            if catch and op not in (ONE, ZERO):
                next_c = c + 1
                # nothing else to check
                if next_c > maxclen:
                    continue
                # if current catch successed at least once
                # next catch can be checked on same token
                if 1 in catch and catch[1]:
                    catchings.setdefault(next_c, {0: {}, 1: {}})
                    catchings[next_c][0].update(catch[1])
                # for `?` and `*`, next catch on same token can
                # be checked even without any previous success
                if op in (ZERO_ONE, ZERO_PLUS) and 0 in catch and catch[0]:
                    catchings.setdefault(next_c, {0: {}, 1: {}})
                    catchings[next_c][0].update(catch[0])
        else:
            if not catch:
                catch = {0: {}, 1: {}}
            if not catch[0] and not catch[1] or c <= head_end:
                catch[1].setdefault(i)
            catch[1].update(catch[0])
            # for `*` and `+`, keep checking same
            # catch saving previous good starts
            if op in (ONE_PLUS, ZERO_PLUS):
                catchings.setdefault(c, {0: {}, 1: {}})
                catchings[c][1] = catch[1]
            next_c = c + 1
            # if in tail or at the end, it is good to match
            if next_c >= tail_start or next_c > maxclen:
                yield from ((s, i + 1) for s in catch[1])
                if next_c > maxclen:
                    continue
            # next catch can be checked on next token
            new_catchings.setdefault(next_c, {0: {}, 1: {}})
            new_catchings[next_c][0].update(catch[1])
            # for `?` and `*`, next catch
            # can be checked on same token
            if op in (ZERO_ONE, ZERO_PLUS):
                catchings.setdefault(next_c, {0: {}, 1: {}})
                catchings[next_c][0].update(catch[0])

    catchings.update(new_catchings)


def _preprocess_pattern(pattern):

    retextitems = []
    relemmaitems = []
    catcheritems = []

    for i, tokenspec in enumerate(pattern):

        if not isinstance(tokenspec, dict):
            raise ValueError(Errors.E154.format())
        for attr, value in {**tokenspec}.items():
            # normalize case
            if attr.islower():
                tokenspec[attr.upper()] = value
                del tokenspec[attr]
            # fix specs
            for fix in [("TEXT", "ORTH"), ("IS_SENT_START", "SENT_START")]:
                if attr != fix[0]:
                    continue
                tokenspec[fix[1]] = value
                del tokenspec[fix[0]]
            if attr not in TOKEN_PATTERN_SCHEMA["items"]["properties"]:
                raise ValueError(Errors.E152.format(attr=attr))
            if not (
                isinstance(value, str)
                or isinstance(value, bool)
                or isinstance(value, int)
                or isinstance(value, dict)
            ):
                raise ValueError(
                    Errors.E153.format(vtype=type(value).__name__)
                )

        op = tokenspec["OP"] if "OP" in tokenspec else ONE
        cf = _catcherfunc_from_tokenspec(tokenspec)
        catcheritems.append((op, cf))

        tregex = _regext_from_tokenspec(tokenspec)
        retextitems.append(tregex)

        lregex = _regexl_from_tokenspec(tokenspec)
        relemmaitems.append(lregex)

    tregex = _regex_from_items(retextitems)
    lregex = _regex_from_items(relemmaitems)

    return (
        _catcher_from_items(catcheritems),
        re.compile(tregex, flags=re.U) if tregex else None,
        re.compile(lregex, flags=re.U) if lregex else None,
    )


def _catcher_from_items(items):
    good_qs = (ONE, ONE_PLUS, ZERO, ZERO_ONE, ZERO_PLUS)
    for q, _ in items:
        if q is None or q in good_qs:
            continue
        keys = ", ".join(good_qs)
        raise ValueError(Errors.E011.format(op=q, opts=keys))
    qsep = (ONE, ONE_PLUS, ZERO)
    head = (i for i, e in enumerate(items) if e[0] in qsep)
    head_end = next(head)
    tail = (i for i, e in enumerate(reversed(items)) if e[0] in qsep)
    tail_start = len(items) - next(tail)
    return (items, head_end, tail_start)


def _catcherfunc_from_tokenspec(tokenspec):
    if not tokenspec:
        return lambda x, _: True
    funcs = []
    for attr, value in tokenspec.items():
        key = json_dumps({attr: value})
        if attr == "_":
            if not isinstance(value, dict):
                raise ValueError(Errors.E154.format())
            funcs.append((key, _evalfunc_from_extensions(value)))
        elif attr == "REGEX":
            funcs.append((key, lambda x, _: True))
        elif attr != "OP":
            funcs.append((key, _evalfunc_from_attr(attr, value)))

    def evalfunc(x, bcmp, cache):
        for k, f in funcs:
            if k not in cache:
                cache.setdefault(k, {})
            res = f(x, cache[k]) == bcmp
            if not res:
                return False
        return True

    bcmp = "OP" not in tokenspec or tokenspec["OP"] != "!"
    return lambda x, cache: evalfunc(x, bcmp, cache)


def _evalfunc_from_attr(attr, value):
    if isinstance(value, dict):
        return _evalfunc_from_predicates(attr, value)
    return lambda x, _: value == _get_token_attr(x, attr)


def _evalfunc_from_extensions(extensions):
    if not isinstance(extensions, dict):
        raise ValueError(Errors.E154.format())
    for ext, value in extensions.items():
        if isinstance(value, dict):
            return _evalfunc_from_predicates(ext, value, True)
        return lambda x, _: x._.get(ext) == value


def _evalfunc_from_predicates(attr, predicates, in_ext=False):
    def evalfunc(x, preds, cache):
        for pred, value in preds.items():
            res = _evalfunc_from_predicate(x, pred, value, attr, cache, in_ext)
            if not res:
                return False
            # func = _evalfunc_from_predicate(pred, value, attr, in_ext)
            # if not func(x):
            # return False
        return True

    preds = {**predicates}
    for pred, value in predicates.items():
        if not isinstance(value, list):
            continue
        preds[pred] = frozenset(value)
    return lambda x, cache: evalfunc(x, preds, cache)


_PFUNC_LOOKUP = {
    "REGEX": lambda x, y: bool(re.search(y, x)),
    "IN": lambda x, y: x in y,
    "NOT_IN": lambda x, y: x not in y,
    "==": lambda x, y: x == y,
    "!=": lambda x, y: x != y,
    ">=": lambda x, y: x >= y,
    "<=": lambda x, y: x <= y,
    ">": lambda x, y: x > y,
    "<": lambda x, y: x < y,
}


def _evalfunc_from_predicate(token, pred, value, attr, cache, in_ext=False):
    val = token._.get(attr) if in_ext else _get_token_attr(token, attr)
    key = val if isinstance(val, str) else str(val)
    if key in cache:
        return cache[key]
    res = _PFUNC_LOOKUP[pred](val, value)
    cache[key] = res
    return res

    # return lambda x: _PFUNC_LOOKUP[pred](
    #     x._.get(attr) if in_ext else _get_token_attr(x, attr), value,
    # )


@lru_cache(None)
def _get_token_attr(token: Token, attr: str):
    if attr == "LEMMA":
        return token.lemma_
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
    elif attr == "HEAD":
        return token.head_
    elif attr == "SENT_START":
        return token.sent_start
    elif attr == "ENT_IOB":
        return token.ent_iob_
    elif attr == "ENT_TYPE":
        return token.ent_type_
    elif attr == "ENT_ID":
        return token.ent_id_
    elif attr == "ENT_KB_ID":
        return token.ent_kb_id_
    elif attr == "LEX_ID":
        return token.lex_id
    elif attr == "ORTH":
        return token.orth_
    elif attr == "LOWER":
        return token.lower_
    elif attr == "SHAPE":
        return token.shape_
    elif attr == "PREFIX":
        return token.prefix_
    elif attr == "SUFFIX":
        return token.suffix_
    elif attr == "LENGTH":
        return len(token)
    elif attr == "CLUSTER":
        return token.cluster
    elif attr == "LANG":
        return token.lang_
    elif token.check_flag(intify_attr(attr)):
        return True
    return False


_REGEX_ONE_TOKEN = r"[^ ]+"


def _regex_from_items(items):
    return (
        # if only about attributes, no regex
        None  # r"[\s\S]+"
        if not items or all(_REGEX_ONE_TOKEN in r for r in items)
        else _regex_wrap_bounds(r"".join([r for r in items if r]), left=True)
    )


def _regext_from_tokenspec(tokenspec):

    content = None
    case_insensitive = False

    if "REGEX" in tokenspec:
        content = tokenspec["REGEX"]
        if isinstance(content, str):
            return content
    elif "LOWER" in tokenspec:
        case_insensitive = True
        content = tokenspec["LOWER"]
    elif "ORTH" in tokenspec:
        content = tokenspec["ORTH"]
    elif "TEXT" in tokenspec:
        content = tokenspec["TEXT"]

    op = tokenspec["OP"] if "OP" in tokenspec else None
    return _regex_from_content(
        content, case_insensitive=case_insensitive, op=op,
    )


def _regexl_from_tokenspec(tokenspec):
    content = tokenspec["LEMMA"] if "LEMMA" in tokenspec else None
    op = tokenspec["OP"] if "OP" in tokenspec else None
    return _regex_from_content(content, op=op)


def _regex_from_content(content, case_insensitive=False, op=None):
    if not content:
        regex = _REGEX_ONE_TOKEN
        if op is not None and op != "!":
            return _regex_wrap_op(op, regex)
        return _regex_wrap_bounds(regex, right=True)

    if isinstance(content, dict):
        if "REGEX" in content:
            return r"[^ ]*?" + content["REGEX"]
        if "IN" in content:
            in_op = "IN"
            wrap_in_op = "1"
        elif "NOT_IN" in content:
            in_op = "NOT_IN"
            wrap_in_op = "!"
        else:
            raise ValueError(Errors.E154.format())
        terms = [re.escape(term) for term in content[in_op]]
        regex = _regex_wrap_op(wrap_in_op, _regex_pipe_terms(terms))

    else:
        regex = re.escape(content)

    if case_insensitive:
        regex = f"(?i:{regex})"

    if op is not None:
        return _regex_wrap_op(op, regex)

    return _regex_wrap_bounds(regex, right=True)


def _regex_pipe_terms(terms):
    return r"".join([r"(?:", r"|".join(terms), r")"])


def _regex_wrap_bounds(text, left=None, right=None):
    return "".join(
        [
            r"(?:\s+|\b|^)" if left else "",
            text,
            r"(?:\s+|\b|$)" if right else "",
        ]
    )


_WRAP_OP_LOOKUP = {
    "*": "(?:\\b{}(?:[^a-zA-Z0-9]+?|\\b|$))*",
    "+": "(?:\\b{}(?:[^a-zA-Z0-9]+?|\\b|$))+",
    "?": "(?:\\b{}(?:[^a-zA-Z0-9]*?|\\b|$))?",
    "!": "(?!\\b{}(?:[^a-zA-Z0-9]+?|\\b|$))[^ ]+",
    "1": "(?:\\b{}(?:[^a-zA-Z0-9]+?|\\b|$))",
}


def _regex_wrap_op(op, text):
    if op not in _WRAP_OP_LOOKUP:
        keys = ", ".join(_WRAP_OP_LOOKUP.keys())
        raise ValueError(Errors.E011.format(op=op, opts=keys))
    return _WRAP_OP_LOOKUP[op].format(text)
