from dataclasses import dataclass
from typing import Callable, Union

import regex as re
from cyac import Trie
from spacy.tokens import Doc, Span, Token

from ..matcher import Matcher
from ..wikigraph import WikiGraph


@dataclass
class Catch:
    pages: list
    score: float
    spans: list


class WikiCatchX:
    def __init__(
        self,
        graph: WikiGraph = None,
        graph_name: str = None,
        max_score: float = None,
        min_score: float = None,
        refresh: bool = None,
        filter_span_func: Callable = None,
    ):
        Doc.set_extension("catches", default=[], force=True)
        self._trie = Trie(ignore_case=True)
        self._trie_pages_map = {}
        self._pages_map = {}
        self.wg = graph or WikiGraph(graph_name)
        self.max_score = max_score or 1.0
        self.min_score = min_score or 0.0
        self.refresh = refresh
        self.filter_span_func = filter_span_func or (lambda x: True)
        self._setup()

    # def _setup_new(self):
    #     for page in self.wg.pages():
    #         title = page["title"]
    #         norm_title = _normalize_title(title)
    #         pages = self._pages_map.setdefault(norm_title, {})
    #         pages.setdefault(page.index)

    def _setup(self):
        for page in self.wg.pages():
            title = page["title"]
            norm_title = _normalize_title(title)
            if norm_title not in self._pages_map:
                self._pages_map[norm_title] = set()
                id_ = self._trie.insert(norm_title)
                self._trie_pages_map[id_] = norm_title
            self._pages_map[norm_title].add(page.index)

    def __call__(self, doc: Doc):
        if doc._.catches and not self.refresh:
            return doc
        idx2i, text = _preprocess(doc, True)
        ac_sep = set([ord("_")])
        maxtlen = len(text)
        catches = {}
        for id_, start_idx, end_idx in self._trie.match_longest(text, ac_sep):
            start_i, end_i = _span_idx2i(start_idx, end_idx, idx2i, maxtlen)
            span = doc[start_i:end_i]
            key = self._trie_pages_map[id_]
            catch = text[start_idx:end_idx]
            if not self.filter_span_func(span):
                continue
            data = catches.setdefault(key, {})
            spans = data.setdefault("spans", set())
            spans.add(span)
            if "score" in data:
                continue
            nfactor = 0
            pids = self._pages_map[key]
            pages = data.setdefault("pages", {})
            for vid in pids:
                vx = self.wg.get_vertex(vid)
                head_vx = self.wg.get_head_vertex(vx)
                if head_vx.index in pages:
                    continue
                if not _is_good_catch(vx, catch):
                    continue
                nfactor += 1
                pages.setdefault(head_vx.index)
            span_score = (1 / nfactor) if nfactor else 0
            if span_score < self.min_score or span_score > self.max_score:
                continue
            data.setdefault("score", span_score)
        matcher = Matcher(doc.vocab)
        catches = list(catches.values())
        for i, catch in enumerate(catches):
            for span in catch["spans"]:
                matcher.add(i, [[{"TEXT": span.text}]])
        for i, start, end in matcher(doc):
            span = doc[start:end]
            catch = catches[i]
            catch["spans"].add(span)
        doc._.catches = [
            Catch(
                pages=list(catch["pages"]),
                score=catch["score"],
                spans=list(catch["spans"]),
            )
            for catch in catches
        ]
        return doc


def _normalize_title(title: str):
    return _remove_title_detailing(title).lower()


def _remove_title_detailing(title: str):
    open_at = title.find("(")
    if open_at < 0:
        return title
    close_at = title.find(")", open_at)
    if close_at < 0:
        return title
    a = title[: open_at - 1]
    b = title[close_at + 1 :]
    return "".join((a, b))


def _preprocess(source: Union[Doc, Span], stopwords: bool):
    idx2i, text = _preprocess_maps(source, stopwords)
    text = re.sub(r"[\n\s\p{P}]", "_", text)
    return idx2i, text


def _preprocess_maps(source: Union[Doc, Span], stopwords: bool):
    idx2i = {}
    text_tokens = []
    curr_length = 0
    num_spaces = 0
    for i, token in enumerate(source):
        pad = num_spaces
        idx = curr_length + pad
        idx2i[idx] = i
        value = _get_token_text_norm(token, stopwords)
        curr_length += len(value)
        value += token.whitespace_
        num_spaces += len(token.whitespace_)
        text_tokens.append(value)
    curr_length += num_spaces
    len_source = len(source)
    idx2i[curr_length] = len_source
    text = "".join(text_tokens)
    return idx2i, text


def _get_token_text_norm(token: Token, stopwords: bool):
    if stopwords and token.is_stop:
        return "_"
    if token.pos_ not in ("NOUN", "PROPN"):
        return token.lower_
    return token.lemma_


def _span_idx2i(start_idx, end_idx, idx2i, maxlen):
    while start_idx not in idx2i and start_idx < maxlen:
        start_idx += 1
    while end_idx not in idx2i and end_idx < maxlen:
        end_idx += 1
    return idx2i[start_idx], idx2i[end_idx]


def _is_good_span_for_catch(span):
    first = span[0]
    bad_pos_tag = ("AUX",)
    good_tag = ("VBG",)
    good_pos = ("NOUN", "PROPN")
    if len(span) == 1:
        if not first.like_num and (
            (first.tag_ in good_tag and first.pos_ not in bad_pos_tag)
            or first.pos_ in good_pos
        ):
            return True
        return
    bad_pos = ("ADP", "DET", "CONJ", "CCONJ", "SCONJ", "NUM")
    if any(token.pos_ in bad_pos for token in span):
        return
    return any(
        token.pos_ in good_pos or token.tag_ in good_tag for token in span
    )


def _is_good_catch(page, catch):
    title = _remove_title_detailing(page["title"])
    pageup_count = sum(1 for c in title if c.isupper())
    catchup_count = sum(1 for c in catch if c.isupper())
    max_caps = catch.count("_") + 1
    diff = abs(pageup_count - catchup_count)
    return diff <= max_caps or diff >= len(catch) - max_caps
