from typing import Any, Dict, List, Tuple

import regex as re
from spacy.attrs import intify_attr
from spacy.errors import Errors, MatchPatternError
from spacy.matcher import Matcher
from spacy.strings import get_string_id
from spacy.tokens.doc import Doc
from spacy.tokens.token import Token
from spacy.util import get_json_validator, validate_json

from ..util import span_idx2i
from ._schemas import TOKEN_PATTERN_SCHEMA

REGEX_ONE_TOKEN = r"[^ ]+"


class REMatcher(object):
    def __init__(self, validate: bool = False, *args, **kwargs):

        self._specs = {}
        self._patterns = {}
        self._callbacks = {}
        self._seen_attrs = set()

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

        self._specs.setdefault(key, [])
        for pattern in patterns:

            spec = _preprocess_pattern(pattern)
            self._specs[key].append(spec)

            attrs = set(attr for token in pattern for attr in token.keys())
            self._seen_attrs.update(attrs)

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
            len(set(("LEMMA", "POS", "TAG")) & self._seen_attrs) > 0
            and not doc.is_tagged
        ):
            raise ValueError(Errors.E155.format())

        if "DEP" in self._seen_attrs and not doc.is_parsed:
            raise ValueError(Errors.E156.format())

        cache = {}
        matches = []
        doclen = len(doc)
        matcher = Matcher(doc.vocab)

        for key, i, start, end in find_re_matches(doc, self._specs):
            norm_key = (
                doc.vocab.strings.add(key)
                if key not in doc.vocab.strings
                else doc.vocab.strings[key]
            )
            candidate = doc[start:end]
            # if doclen == len(candidate):
            #     matcher.add(norm_key, [self._patterns[key][i]])
            #     continue
            catcher = self._specs[key][i][0]
            matches.extend(
                (norm_key, start + s, start + e) for s, e in catcher(candidate, cache)
            )
            # if any("REGEX" in token for token in self._patterns[key][i]):
            #     matches.append((key, start, end))
            #     continue
            # span_matcher = Matcher(doc.vocab)
            # span_matcher.add(norm_key, [self._patterns[key][i]])
            # matches.extend(
            #     (k, start + s, start + e)
            #     for k, s, e in span_matcher(candidate.as_doc())
            # )

        # for norm_key, start, end in matcher(doc):
        #     matches.append((norm_key, start, end))

        if best_sort:
            matches.sort(key=lambda x: (x[1], -x[2], x[0]))

        for i, match in enumerate(matches):
            key = doc.vocab.strings[match[0]]
            on_match = self._callbacks.get(key, None)
            if on_match is not None:
                on_match(self, doc, i, matches)

        return matches


def _preprocess_pattern(pattern):

    regextitems = []
    regexlitems = []
    catcheritems = []
    specmax = len(pattern)

    for i, tokenspec in enumerate(pattern):

        if not isinstance(tokenspec, dict):
            raise ValueError(Errors.E154.format())
        for attr, value in {**tokenspec}.items():
            # normalize case
            if attr.islower():
                tokenspec[attr.upper()] = value
                del tokenspec[attr]
            # normalize text
            if attr == "TEXT":
                tokenspec["ORTH"] = value
                del tokenspec["TEXT"]
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

        op = tokenspec["OP"] if "OP" in tokenspec else "1"
        cf = _catcherfunc_from_tokenspec(tokenspec) or None
        catcheritems.append((op, cf))

        tregex = _regext_from_tokenspec(tokenspec, i == 0)
        regextitems.append(tregex)

        lregex = _regexl_from_tokenspec(tokenspec, i == 0)
        regexlitems.append(lregex)

    tregex = _regex_from_items(regextitems)
    lregex = _regex_from_items(regexlitems)

    return (
        _catcher_from_items(catcheritems),
        re.compile(tregex, flags=re.U | re.I) if tregex else None,
        re.compile(lregex, flags=re.U | re.I) if lregex else None,
    )


def _catcher_from_items(catcheritems):
    good_ops = ["1", "!", "?", "*", "+"]
    for op, _ in catcheritems:
        if op is None or op in good_ops:
            continue
        keys = ", ".join(good_ops)
        raise ValueError(Errors.E011.format(op=op, opts=keys))

    def catch_matches(candidate, cache, catcheritems):
        catchings = {}
        maxclen = len(catcheritems) - 1
        headlen = next(
            i for i, e in enumerate(catcheritems) if e[0] in ["1", "+"]
        )
        taillen = next(
            i
            for i, e in enumerate(reversed(catcheritems))
            if e[0] in ["1", "+"]
        )
        tailclen = maxclen - taillen
        for i, token in enumerate(candidate):
            c = 0
            new_catchings = {}
            while c <= maxclen:
                if c > headlen and c not in catchings:
                    c += 1
                    continue
                op, cf = catcheritems[c]
                if not cf(token, cache):

                    if op in ["1", "!", "+"]:
                        if c in catchings:
                            if catchings[c][1]:
                                next_c = c + 1
                                if next_c > tailclen:
                                    if c in catchings and catchings[c][1]:
                                        yield from (
                                            (s, i + 1) for s in catchings[c][1]
                                        )
                                        del catchings[c]
                                    if next_c > maxclen:
                                        c += 1
                                        continue
                                if next_c not in new_catchings:
                                    new_catchings[next_c] = {0: {}, 1: {}}
                                new_catchings[next_c][0].update(
                                    catchings[c][1]
                                )

                            del catchings[c]

                    elif op in ["?", "*"]:
                        next_c = c + 1
                        if next_c > tailclen:
                            if c in catchings and catchings[c][1]:
                                yield from ((s, i) for s in catchings[c][1])
                                del catchings[c]
                            if next_c > maxclen:
                                c += 1
                                continue
                        if next_c not in new_catchings and next_c <= maxclen:
                            new_catchings[next_c] = {0: {}, 1: {}}
                        if c in new_catchings and new_catchings[c][1]:
                            new_catchings[next_c][0].update(catchings[c][1])
                            del catchings[c]
                        else:
                            new_catchings[next_c][0].setdefault(i)

                else:

                    if op in ["?", "1", "!"]:
                        next_c = c + 1
                        if next_c > tailclen:
                            if c <= headlen:
                                if c not in catchings:
                                    catchings[c] = {0: {}}
                                catchings[c][0].setdefault(i)
                            if c in catchings and catchings[c][0]:
                                yield from (
                                    (s, i + 1) for s in catchings[c][0]
                                )
                                del catchings[c]
                            if next_c > maxclen:
                                c += 1
                                continue
                        if next_c not in new_catchings and next_c <= maxclen:
                            new_catchings[next_c] = {0: {}, 1: {}}
                        if c in catchings and catchings[c][0]:
                            new_catchings[next_c][0].update(catchings[c][0])
                            del catchings[c]
                        else:
                            new_catchings[next_c][0].setdefault(i)

                    elif op in ["*", "+"]:
                        next_c = c + 1
                        if next_c > tailclen:
                            if c <= headlen:
                                if c not in catchings:
                                    catchings[c] = {1: {}}
                                catchings[c][1].setdefault(i)
                            if c in catchings:
                                yield from (
                                    (s, i + 1)
                                    for starts in catchings[c].values()
                                    for s in starts
                                )
                            if next_c > maxclen:
                                c += 1
                                continue
                        for el in [catchings, new_catchings]:
                            if c not in el:
                                el[c] = {0: {}, 1: {}}
                            if next_c not in el and next_c <= maxclen:
                                el[next_c] = {0: {}, 1: {}}
                            if c in el and catchings[c][1]:
                                el[next_c][0].update(catchings[c][1])
                            if c <= headlen:
                                el[c][1].setdefault(i)
                            el[c][1] = {**el[c][0], **el[c][1]}

                c += 1
            catchings = {**new_catchings, **catchings}
    return lambda x, cache: catch_matches(x, cache, catcheritems)


def _catcherfunc_from_tokenspec(tokenspec):
    if not tokenspec:
        return lambda x: True
    funcs = []
    for attr, value in tokenspec.items():
        if attr == "_":
            if not isinstance(value, dict):
                raise ValueError(Errors.E154.format())
            funcs.append(_evalfunc_from_extensions(value))
        elif attr == "REGEX":
            funcs.append(lambda x: True)
        elif attr not in ["REGEX", "OP"]:
            funcs.append(_evalfunc_from_attr(attr, value))
    def evalfunc(x, cache, bcmp):
        for f in funcs:
            if f(x, cache) != bcmp:
                return False
        return True
    bcmp = "OP" not in tokenspec or tokenspec["OP"] != "!"
    return lambda x, cache: evalfunc(x, cache, bcmp)


def _evalfunc_from_attr(attr, value):
    if isinstance(value, dict):
        return _evalfunc_from_predicates(attr, value)
    return lambda x: value == get_token_attr(x, attr)


def _evalfunc_from_extensions(extensions):
    if not isinstance(extensions, dict):
        raise ValueError(Errors.E154.format())
    for ext, value in extensions.items():
        if isinstance(value, dict):
            return _evalfunc_from_predicates(ext, value, True)
        return lambda x: x._.get(ext) == value


def _evalfunc_from_predicates(attr, predicates, in_ext=False):
    def evalfunc(x, cache, preds):
        index = x.i
        if index not in cache:
            cache[index] = {}
        cachei = cache[index]
        for pred, value in preds.items():
            key = "".join([attr, pred, *value])
            if key in cachei and not cachei[key]:
                return False
            res = _evalfunc_from_predicate(pred, value, attr, in_ext)(x)
            cachei.setdefault(attr, res)
            if not res:
                return False
        return True
    new_predicates = {**predicates}
    for pred, value in predicates.items():
        if not isinstance(value, list):
            continue
        new_predicates[pred] = {*value}
    return lambda x, cache: evalfunc(x, cache, new_predicates)


_PREDICATES_TABLE = {
    "REGEX": lambda x, y: bool(re.match(y, x)),
    "IN": lambda x, y: x in y,
    "NOT_IN": lambda x, y: x not in y,
    "==": lambda x, y: x == y,
    "!=": lambda x, y: x != y,
    ">=": lambda x, y: x >= y,
    "<=": lambda x, y: x <= y,
    ">": lambda x, y: x > y,
    "<": lambda x, y: x < y,
}


def _evalfunc_from_predicate(pred, value, attr, in_ext=False):
    return lambda x: _PREDICATES_TABLE[pred](
        x._.get(attr) if in_ext else get_token_attr(x, attr), value,
    )


def get_token_attr(token: Token, attr: str):
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


def _regex_from_items(items):
    return (
        # if only about attributes, no regex
        None  # r"[\s\S]+"
        if not items or all(REGEX_ONE_TOKEN in r for r in items)
        else r"".join([r for r in items if r])
    )


def _regext_from_tokenspec(tokenspec, is_first=False):

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
        content, case_insensitive=case_insensitive, is_first=is_first, op=op,
    )


def _regexl_from_tokenspec(tokenspec, is_first=False):
    content = tokenspec["LEMMA"] if "LEMMA" in tokenspec else None
    op = tokenspec["OP"] if "OP" in tokenspec else None
    return _regex_from_content(content, is_first=is_first, op=op)


def _regex_from_content(
    content, case_insensitive=False, is_first=False, op=None
):
    if not content:
        regex = REGEX_ONE_TOKEN
        if op is not None and op != "!":
            return _regex_wrap_op(op, regex)
        return _regex_wrap_bounds(regex, is_first)

    if isinstance(content, dict):
        if "REGEX" in content:
            return content["REGEX"]
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

    if op is not None:
        return _regex_wrap_op(op, regex)

    return _regex_wrap_bounds(regex, is_first)


def _regex_pipe_terms(terms):
    return r"".join([r"(?:", r"|".join(terms), r")"])


def _regex_wrap_bounds(text, is_first=False):
    return (r"(?:\W+|\b|^)" if is_first else r"") + text + r"(?:\W+|\b|$)"


def _regex_wrap_op(op, text):
    lookup = {
        "*": f"(?:{text}(?:\\W+|\\b|$))*",
        "+": f"(?:{text}(?:\\W+|\\b|$))+",
        "?": f"(?:{text}(?:\\W+|\\b|$))?",
        "!": f"(?!{text}(?:\\W+|\\b|$))[^ ]+",
        "1": f"(?:{text}(?:\\W+|\\b|$))",
    }
    if op not in lookup:
        keys = ", ".join(lookup.keys())
        raise ValueError(Errors.E011.format(op=op, opts=keys))
    return lookup[op]


def find_re_matches(
    doc: Doc, specs: Dict[str, List[Tuple[Dict[str, Any]]]]
) -> List[Tuple[str, int, int, int]]:
    doc_text = doc.text
    maxdlen = len(doc)
    maxtlen = len(doc_text)
    for key, values in specs.items():
        for i, spec in enumerate(values):
            if not spec[1]:
                yield (key, i, 0, maxdlen)
                continue
            for match in spec[1].finditer(doc_text):
                start, end = span_idx2i(
                    doc, match.start(), match.end(), maxtlen
                )
                if start == end:
                    continue
                if not spec[2] or spec[2].search(
                    " ".join([t.lemma_ for t in doc[start:end]])
                ):
                    yield (key, i, start, end)
