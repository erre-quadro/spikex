import regex as re
from spacy.tokens import Doc

from spikex.defaults import spacy_version

from .fragment import Fragment
from .nbmodel import NBModel

if spacy_version >= 3:
    from spacy.language import Language

    @Language.factory("sentx")
    def create_sentx(nlp, name):
        return SentX()


class SentX:
    def __init__(self):
        self.model = NBModel.load()

    def __call__(self, doc: Doc):
        fragments = _get_fragments(doc)
        self.model.classify(fragments)
        start_token_ids = _sent_start_token_ids(fragments)
        for token in doc:
            token.is_sent_start = token.i in start_token_ids
        return doc


def _sent_start_token_ids(fragments):
    # iterate all tokens that end a sentence
    # according to predictions or labels
    thresh = 0.5
    is_next_start = True
    start_token_ids = []
    for frag in fragments:
        if is_next_start:
            start_token_ids.append(frag.first_token.i)
            # continue
        is_next_start = (
            frag.label > thresh or frag.prediction > thresh or frag.is_sent_end
        )
    return start_token_ids


SAFE_ACRONYMS = re.compile(
    r"^(tm|TM|Std|Nor|Fig|FIG|Figs|FIGS|pat|Pat|ser|Ser|No|Num|eg|[1-9][0-9])$"
)
SAFE_ABBRS = re.compile(r"(?:^[a-zA-Z]{1,3}\.)")
SPECIAL_SENT_STARTERS = re.compile(
    r"((?:[a-zèéòàìù]+|[A-ZÈÉÒÙÀÌ]{3,}|[0-9]\s*\))(?:\s*\))?)?\s*"
    r"((?:The|This|That|Those|These|Who|When|What|Which|Where|Whose)\s*"
    r"(?:[a-z]|[A-Z][a-zèéòàìù]+\s+[a-z])?)"
)


def _get_fragments(doc):
    fragments = []
    curr_tokens = []
    curr_frag = None
    last_frag = None
    for token in doc:
        curr_tokens.append(token)
        if len(curr_tokens) == 1:
            continue
        prev_token = curr_tokens[-2]
        split_at_last = SPECIAL_SENT_STARTERS.search(token.text) and (
            (
                prev_token.pos_
                and prev_token.pos_ in ("NOUN", "PROPN", "ADJ", "ADV")
                or prev_token.tag_
                and prev_token.tag_ in ("NN", "NNS", "NNP", "NNPS", "JJ", "RB")
            )
            or "\n" in prev_token.text
        )
        if not _is_sentence_boundary(token, prev_token) and not split_at_last:
            continue
        last_frag = curr_frag
        if split_at_last:
            curr_tokens = curr_tokens[:-1]
        curr_frag = Fragment([*curr_tokens])
        curr_frag.is_sent_end = True
        curr_frag.label = int("<S>" in token.text)
        curr_tokens = []
        if split_at_last:
            curr_tokens.append(token)
        if last_frag is not None:
            last_frag.next_frag = curr_frag
            fragments.append(last_frag)
    # last frag
    if len(curr_tokens) > 0:
        if curr_frag is not None:
            fragments.append(curr_frag)
        curr_frag = Fragment(curr_tokens)
        curr_frag.label = int("<S>" in curr_tokens[-1].text)
    if curr_frag is not None:
        curr_frag.is_sent_end = True
        fragments.append(curr_frag)
    return fragments


def _is_sentence_boundary(token, prev_token):
    c = _unannotate(token.text)
    prev_word = prev_token.text
    if SAFE_ACRONYMS.search(prev_word) or SAFE_ABBRS.search(prev_word):
        return
    if (c.endswith(".") or re.match(r".*\.[\"')\]]*$", c)) and not (
        SAFE_ACRONYMS.search(c) or SAFE_ABBRS.search(c)
    ):
        return True


def _unannotate(t):
    # get rid of a tokenized word's annotations
    return re.sub(r"(<A>)?(<E>)?(<S>)?$", "", t)
