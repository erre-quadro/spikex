from spacy.tokens import Doc, Span

from ..wikigraph import WikiGraph


class WikiPageX:
    """
    Detect spans which match with Wikipedia pages, based on a
    specific `WikiGraph`.
    """

    def __init__(self, wikigraph: WikiGraph) -> None:
        Doc.set_extension("wiki_spans", default=[])
        Span.set_extension("wiki_pages", default=[])
        self._wg = wikigraph

    def __call__(self, doc: Doc):
        idx2i, text = _preprocess_doc(doc)
        maxtlen = len(text)
        for start_idx, end_idx, pages in self._wg.find_pages(text):
            start_i, end_i = _span_idx2i(start_idx, end_idx, idx2i, maxtlen)
            if start_i >= end_i:
                continue
            span = doc[start_i:end_i]
            for p in pages:
                vx = self._wg.get_vertex(p)
                span._.wiki_pages.append((p, vx["title"]))
            doc._.wiki_spans.append(span)
        return doc


def _preprocess_doc(doc):
    idx2i = {}
    curr_idx = 0
    text_tokens = []
    for i, token in enumerate(doc):
        idx2i[curr_idx] = i
        value = token.lemma_ if token.pos_ == "NOUN" else token.text
        value += token.whitespace_
        text_tokens.append(value)
        curr_idx += len(value)
    idx2i[curr_idx] = len(doc)
    text = "".join(text_tokens)
    return idx2i, text.replace(" ", "_")


def _span_idx2i(start_idx, end_idx, idx2i, maxlen):
    while start_idx not in idx2i and start_idx < maxlen:
        start_idx += 1
    while end_idx not in idx2i and end_idx < maxlen:
        end_idx += 1
    if start_idx == end_idx:
        end_i = idx2i[end_idx]
        return end_i - 1, end_i
    return idx2i[start_idx], idx2i[end_idx]
