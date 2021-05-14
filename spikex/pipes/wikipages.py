import regex as re
from spacy.tokens import Doc, Span

from spikex.defaults import spacy_version

from ..wikigraph import WikiGraph

if spacy_version >= 3:
    from spacy.language import Language

    @Language.factory("wikipagex")
    def create_wikipagex(nlp, name):
        return WikiPageX()


_TEXT_SEP = "_"
_PATTERN_SEP = re.compile(r"[\s\n]")


class WikiPageX:
    """
    Detect spans which match with Wikipedia pages, based on a
    specific `WikiGraph`.
    """

    def __init__(self, wikigraph: WikiGraph) -> None:
        Doc.set_extension("wiki_spans", default=[], force=True)
        Span.set_extension("wiki_pages", default=[], force=True)
        self._wg = wikigraph

    def __call__(self, doc: Doc):
        idx2i, text = _preprocess_doc(doc)
        maxlen = len(text)
        for start_idx, end_idx, pages in self._wg.find_pages(text):
            # fix ending at whitespace
            if (
                end_idx not in idx2i
                and end_idx < maxlen
                and text[end_idx] == _TEXT_SEP
            ):
                end_idx += 1
            if start_idx not in idx2i or end_idx not in idx2i:
                continue
            span = doc[idx2i[start_idx] : idx2i[end_idx]]
            span._.wiki_pages = pages
            doc._.wiki_spans.append(span)
        return doc


def _preprocess_doc(doc):
    idx2i = {}
    curr_idx = 0
    text_tokens = []
    for i, token in enumerate(doc):
        idx2i[curr_idx] = i
        value = token.lemma_ if token.tag_ in ("NN", "NNS") else token.text
        value += token.whitespace_
        text_tokens.append(value)
        curr_idx += len(value)
    idx2i[curr_idx] = len(doc)
    text = "".join(text_tokens)
    return idx2i, _PATTERN_SEP.sub(_TEXT_SEP, text)
