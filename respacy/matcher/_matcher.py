import regex as re
from spacy.attrs import DEP, LEMMA, POS, TAG, intify_attr
from spacy.errors import Errors, MatchPatternError
from spacy.tokens import Doc, Token
from spacy.util import get_json_validator, validate_json

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
            patternspec = _preprocess_pattern(pattern)
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

    def __call__(self, doc: Doc):
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

        matches = []
        seen = set()
        tokens = [token for token in doc]
        for match in find_matches(tokens, self._specs):
            if match in seen:
                continue
            seen.add(match)
            matches.append(match)
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


def find_matches(tokens, specs):
    attrs_map = {}
    for key, patternspecs in specs.items():
        for i, patternspec in enumerate(patternspecs):
            candidates = [(0, len(tokens))]
            for attr, (respec, is_extension) in patternspec.items():
                if attr not in attrs_map:
                    attrs_map[attr] = _attr2map(attr, tokens, is_extension)
                i2idx, idx2i, text = attrs_map[attr]
                maxlen = len(text)
                new_candidates = []
                for candidate in candidates:
                    start_idx = i2idx[candidate[0]]
                    end_idx = i2idx[candidate[1]]
                    curr_text = text[start_idx:end_idx]
                    print(respec, curr_text)
                    for match in respec.finditer(curr_text):
                        print(respec, match)
                        start = start_idx + match.start()
                        if text[start] == " ":
                            start += 1
                        if start > 0 and text[start - 1] != " ":
                            start = text.find(" ", start) + 1
                        end = start_idx + match.end()
                        if end < maxlen and text[end] == " ":
                            end += 1
                        if end < maxlen and text[end - 1] != " ":
                            end = text.find(" ", end) + 1
                            if end == 0:
                                end = maxlen
                        new_candidate = (
                            idx2i[start],
                            idx2i[end],
                        )
                        new_candidates.append(new_candidate)
                candidates = new_candidates
            yield from (
                (key, candidate[0], candidate[1]) for candidate in candidates
            )


def _attr2map(attr, tokens, is_extension):
    i2idx = {}
    idx2i = {}
    text_tokens = []
    curr_length = 0
    nspaces = 0
    for i, token in enumerate(tokens):
        value = str(
            token._.get(attr)
            if is_extension
            else _get_right_token_attr(token, attr)
        )
        text_tokens.append(value)
        idx = curr_length + i
        i2idx[i] = idx
        idx2i[idx] = i
        curr_length += len(value)
        nspaces = i
    curr_length += nspaces
    i2idx[len(tokens)] = curr_length
    idx2i[curr_length] = len(tokens)
    return (i2idx, idx2i, " ".join(text_tokens))


def _preprocess_pattern(pattern):
    attrspecs = {}
    for tokenspec in pattern:
        if not isinstance(tokenspec, dict):
            raise ValueError(Errors.E154.format())
        for attr, value in {**tokenspec}.items():
            # normalize attributes
            if attr.islower():
                old_attr = attr
                attr = attr.upper()
                tokenspec[attr] = value
                del tokenspec[old_attr]
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
            if attr == "OP":
                continue
            if attr == "_" and not isinstance(value, dict):
                raise ValueError(Errors.E154.format())
            if attr == "REGEX":
                attr = "TEXT"
            new_attrs = value.keys() if attr == "_" else [attr]
            for new_attr in new_attrs:
                attrspecs.setdefault(new_attr, ([None] * len(pattern), False))
    for i, tokenspec in enumerate(pattern):
        new_attrspecs = _tokenspec2attrspecs(tokenspec)
        _align_attrspecs(i, attrspecs, new_attrspecs)
    return _attrspecs2patternspec(attrspecs)


_REGEX_ONE_TOKEN = r"[^ ]+"
_REGEX_TOKEN_START = r"(?:\b|[ ]|^)"
_REGEX_TOKEN_END = "(?({})(?:\\b|[ ]|$)|)"
_REGEX_TOKEN_DELIM = "(?({})(?:[ ]|^|$)|)"


def _attrspecs2patternspec(attrspecs):
    patternspec = {}
    for attr, (respecs, is_extension) in attrspecs.items():
        regex = "".join(
            [
                respec if i == 0 else _REGEX_TOKEN_DELIM.format(i) + respec
                for i, respec in enumerate(respecs)
            ]
        )
        regex = "".join(
            [_REGEX_TOKEN_START, regex, _REGEX_TOKEN_END.format(len(respecs))]
        )
        flags = re.U
        if attr in ["LENGTH", "LOWER"]:
            flags |= re.I
        patternspec[attr] = (re.compile(regex, flags=flags), is_extension)
    return {
        k: v
        for k, v in sorted(
            patternspec.items(),
            key=lambda x: x[0] not in ["LEMMA", "LOWER", "TEXT"],
        )
    }


def _align_attrspecs(i, attrspecs, new_attrspecs):
    for (
        new_attr,
        (new_respec, op, new_is_extension),
    ) in new_attrspecs.items():
        for attr, (respecs, is_extension) in {**attrspecs}.items():
            if respecs[i] is not None and attr != new_attr:
                continue
            if attr == new_attr:
                respecs[i] = new_respec or _REGEX_ONE_TOKEN
                attrspecs[attr] = (respecs, new_is_extension)
            else:
                respecs[i] = _re_wrapop(op, _REGEX_ONE_TOKEN)


def _tokenspec2attrspecs(tokenspec):
    if "REGEX" in tokenspec:
        return {"TEXT": (_re_wrapop("1", tokenspec["REGEX"]), None, None)}
    if not tokenspec:
        return {None: (None, "1", None)}
    if "OP" in tokenspec and len(tokenspec) == 1:
        return {None: (None, tokenspec["OP"], None)}
    attr_op = tokenspec["OP"] if "OP" in tokenspec else "1"
    tok_op = attr_op or "1" if attr_op != "!" else "1"
    respecs = {
        **_tokenspec2extenspecs(tokenspec),
        **_tokenspec2nativspecs(tokenspec),
    }
    return {
        attr: (_re_wrapop(attr_op, respec), tok_op, is_ext)
        for attr, (respec, is_ext) in {**respecs}.items()
    }


def _tokenspec2extenspecs(spec):
    if not isinstance(spec.get("_", {}), dict):
        raise ValueError(Errors.E154.format())
    return _tokenspec2nativspecs(spec.get("_", {}), True)


def _tokenspec2nativspecs(spec, is_extension=False):
    pred2func = {
        "REGEX": _predicate2regex,
        "IN": _predicate2setmember,
        "NOT_IN": _predicate2setmember,
        "==": _predicate2comparison,
        "!=": _predicate2comparison,
        ">=": _predicate2comparison,
        "<=": _predicate2comparison,
        ">": _predicate2comparison,
        "<": _predicate2comparison,
    }
    respecs = {}
    for attr, value in spec.items():
        if attr in ["_", "OP"]:
            continue
        if isinstance(value, int):
            value = str(value)
        regex_list = (
            [pred2func[pred](pred, arg) for pred, arg in value.items()]
            if isinstance(value, dict)
            else [re.escape(value) if attr != "REGEX" else value]
        )
        for regex in regex_list:
            respecs[attr] = (regex, is_extension)
    return respecs


def _predicate2regex(_, argument):
    # re.sub works bad with raw strings
    split = re.split(r"(?:(?<!\[|\\)\^|(?<!\\)\$)", argument)
    merge = "".join(split)
    return merge if len(split) > 1 else "".join([r"[^ ]*?", merge, r"[^ ]*?"])


def _predicate2setmember(predicate, argument):
    pipe = argument[0] if len(argument) == 1 else _re_pipe(argument)
    if predicate == "NOT_IN":
        return _re_wrapop("!", pipe)
    return pipe


def _predicate2comparison(predicate, argument):
    return _re_toklen(predicate, argument)


def _re_pipe(terms):
    pipe = r"|".join((re.escape(term) for term in terms))
    return r"".join([r"(?:", pipe, r")"])


_WRAPOP_LOOKUP = {
    "1": "({})",
    "+": "({}\\W*)+",
    "!": "(?!{})([^ ]+)",
    "?": "({})?",
    "*": "({}\\W*)*",
}


def _re_wrapop(op, content):
    if op is None:
        return content
    if op not in _WRAPOP_LOOKUP:
        keys = ", ".join(_WRAPOP_LOOKUP.keys())
        raise ValueError(Errors.E011.format(op=op, opts=keys))
    return _WRAPOP_LOOKUP[op].format(content)


def _re_toklen(pred, length):
    preds = ("==", "!=", ">=", "<=", ">", "<")
    if pred not in preds:
        raise ValueError(Errors.E126.format(bad=pred, good=preds))
    if pred == "==":
        return "([^ ]{{{}}}+)".format(length)
    elif pred == "!=":
        return "([^ ]{{1,{}}}+|[^ ]{{{},}}+)".format(length - 1, length + 1)
    elif pred == ">=":
        return "([^ ]{{{},}}+)".format(length)
    elif pred == "<=":
        return "([^ ]{{1,{}}}+)".format(length)
    elif pred == ">":
        return "([^ ]{{{},}}+)".format(length + 1)
    elif pred == "<":
        return "([^ ]{{1,{}}}+)".format(length - 1)


def _get_right_token_attr(token: Token, attr: str):
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
