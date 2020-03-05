from typing import Any, Dict, List, Tuple

import regex as re
from spacy.errors import Errors, MatchPatternError
from spacy.matcher import Matcher
from spacy.tokens import Doc, Token
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
            if doclen == len(candidate):
                matcher.add(
                    norm_key, [self._patterns[key][i]]
                )
                continue
            catcher = self._specs[key][i][0]
            matches.extend((norm_key, s, e) for s, e in catcher(candidate))

        for norm_key, start, end in matcher(doc):
            matches.append((norm_key, start, end))

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

    def catch_matches(candidate, _catcheritems):
        cs = candidate[0].i
        for i in range(len(candidate)):
            c = 0
            end = 0
            lastm = 0
            optional = []
            maxclen = len(_catcheritems)
            for token in candidate[i:]:
                if c >= maxclen and not optional:
                    break
                cc = c
                is_match = False
                while cc < maxclen and not is_match:
                    op, cf = _catcheritems[cc]
                    if cf is None:
                        if op == "!":
                            break
                        if not optional:
                            c = cc + 1
                            end = lastm = token.i
                        is_match = True
                    elif (
                        op == "1" and cf(token) or op == "!" and not cf(token)
                    ):
                        c = cc + 1
                        optional = []
                        end = lastm = token.i
                        is_match = True
                    elif op == "+" and cf(token):
                        c = cc + 1
                        end = lastm = token.i
                        optional = [(op, cf)]
                        is_match = True
                    elif op == "?" or op == "*":
                        cc += 1
                        optional.insert(0, (op, cf))
                    else:
                        break

                if is_match:
                    continue

                keep_until = -1
                for idx, (oop, ocf) in enumerate(optional):
                    if not ocf(token):
                        continue
                    if oop == "?":
                        c += 1
                        keep_until = idx
                    else:
                        keep_until = idx + 1
                    optional = optional[:keep_until]
                    break
                if keep_until < 0:
                    break
                end = token.i

            check_op = lambda x: x in ["1", "!", "+"]
            if c < maxclen and any(
                check_op(el[0]) for el in _catcheritems[c:]
            ):
                continue
            rng = range(lastm, end + 1) if lastm <= end else range(end + 1)
            for idx in rng:
                yield (cs + i, idx + 1)

    return lambda x: catch_matches(x, catcheritems)


def _catcherfunc_from_tokenspec(tokenspec):
    if not tokenspec:
        return
    funcs = []
    for attr, value in tokenspec.items():
        if attr == "_":
            if not isinstance(value, dict):
                raise ValueError(Errors.E154.format())
            funcs.append(_evalfunc_from_extensions(value))
        elif attr not in ["REGEX", "OP"]:
            funcs.append(_evalfunc_from_attr(attr, value))
    return lambda x: all(f(x) for f in funcs)


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


def _evalfunc_from_predicates(attr, predicates, from_extension=False):
    return lambda x: all(
        _evalfunc_from_predicate(pred, attr, args, from_extension)(x)
        for pred, args in predicates.items()
    )


def _evalfunc_from_predicate(pred, attr, args, from_extension=False):
    predicates_table = {
        "REGEX": lambda x, y: re.match(y, x),
        "IN": lambda x, y: x in y,
        "NOT_IN": lambda x, y: x not in y,
        "==": lambda x, y: x == y,
        "!=": lambda x, y: x != y,
        ">=": lambda x, y: x >= y,
        "<=": lambda x, y: x <= y,
        ">": lambda x, y: x > y,
        "<": lambda x, y: x < y,
    }
    return lambda x: predicates_table[pred](
        x._.get(attr) if from_extension else get_token_attr(x, attr), args,
    )


def get_token_attr(token: Token, attr: str):
    if attr == "LENGTH":
        return len(token)
    fix_attr = attr.lower() + "_"
    if not hasattr(token, fix_attr):
        fix_attr = attr.lower()
    if not hasattr(token, fix_attr):
        raise ValueError(Errors.E153.format(vtype=attr))
    return getattr(token, fix_attr)


def _regex_from_items(items):
    return (
        # if only about attributes, no regex
        None  # r"[\s\S]+"
        if not items or all(REGEX_ONE_TOKEN in r for r in items)
        else r"".join([r for r in items if r])
    )


def _regext_from_tokenspec(tokenspec, is_first=False):

    content = None
    no_escape = False
    case_insensitive = False

    if "REGEX" in tokenspec:
        no_escape = True
        content = tokenspec["REGEX"]
    elif "LOWER" in tokenspec:
        case_insensitive = True
        content = tokenspec["LOWER"]
    elif "ORTH" in tokenspec:
        content = tokenspec["ORTH"]
    elif "TEXT" in tokenspec:
        content = tokenspec["TEXT"]

    op = tokenspec["OP"] if "OP" in tokenspec else None
    return _regex_from_content(
        content,
        no_escape=no_escape,
        case_insensitive=case_insensitive,
        is_first=is_first,
        op=op,
    )


def _regexl_from_tokenspec(tokenspec, is_first=False):
    content = tokenspec["LEMMA"] if "LEMMA" in tokenspec else None
    op = tokenspec["OP"] if "OP" in tokenspec else None
    return _regex_from_content(content, is_first=is_first, op=op)


def _regex_from_content(
    content, no_escape=False, case_insensitive=False, is_first=False, op=None
):
    regex = None
    if not content:
        regex = REGEX_ONE_TOKEN
        if op is not None and op != "!":
            return _regex_wrap_op(op, regex)
        return _regex_wrap_bounds(regex, is_first)

    if isinstance(content, dict):
        if "REGEX" in content:
            return content["REGEX"]
        in_op = None
        exclude = False
        if "IN" in content:
            in_op = "IN"
        elif "NOT_IN" in content:
            in_op = "NOT_IN"
            exclude = True
        else:
            raise ValueError(Errors.E154.format())
        regex = _regex_pipe_terms(
            (re.escape(t) if not no_escape else t for t in content[in_op]),
            exclude=exclude,
            case_insensitive=case_insensitive,
        )

    if not regex:
        regex = re.escape(content) if not no_escape else content
        if case_insensitive:
            regex = _regex_case_insensitive(regex)

    if op is not None:
        return _regex_wrap_op(op, regex)

    return _regex_wrap_bounds(regex, is_first)


def _regex_case_insensitive(text):
    return text  # "".join([f"[{c.upper()}{c.lower()}]" for c in text])


def _regex_pipe_terms(terms, exclude=False, case_insensitive=False):
    return r"".join(
        [
            r"(?",
            r"!" if exclude else r":",
            r"|".join(
                [_regex_case_insensitive(term) for term in terms]
                if case_insensitive
                else terms
            ),
            r")",
        ]
    )


def _regex_wrap_bounds(text, is_first=False):
    return (r"(?:\W+|\b|^)" if is_first else r"") + text + r"(?:\W+|\b|$)"


def _regex_wrap_op(op, text):
    lookup = {
        "*": f"(?:{text}\\W*)*",
        "+": f"(?:{text}\\W*)+",
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
                if not spec[2] or spec[2].search(
                    " ".join([t.lemma_ for t in doc[start:end]])
                ):
                    yield (key, i, start, end)
