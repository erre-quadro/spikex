from dataclasses import dataclass
from typing import Callable, Union

import regex as re
from spacy.tokens import Doc, Span, Token
from srsly import pickle_loads

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
        filter_span: Callable = None,
    ):
        Doc.set_extension("catches", default=[], force=True)
        self.wg = graph or WikiGraph(graph_name)
        self.max_score = max_score or 1.0
        self.min_score = min_score or 0.0
        self.refresh = refresh
        self.filter_span = filter_span or (lambda x: True)

    def __call__(self, doc: Doc):
        if doc._.catches and not self.refresh:
            return doc
        idx2i, text = _preprocess(doc, True)
        maxtlen = len(text)
        catches = {}
        for start_idx, end_idx, pages in self._wg.find_pages(text):
            print(text[start_idx:end_idx])
            start_i, end_i = _span_idx2i(start_idx, end_idx, idx2i, maxtlen)
            if start_i >= end_i:
                continue
            span = doc[start_i:end_i]
            key = self._trie_pages_map[id_]
            if not self.filter_span(span):
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
                if vx.index in pages:
                    continue
                nfactor += 1
                pages.setdefault(vx.index)
            span_score = (1 / nfactor) if nfactor else 0
            if span_score < self.min_score or span_score > self.max_score:
                del catches[key]
                continue
            data.setdefault("score", span_score)
        idx2data = {}
        matcher = Matcher(doc.vocab)
        catches = list(catches.values())
        for i, catch in enumerate(catches):
            for span in catch["spans"]:
                print("->", span)
                matcher.add(i, [[{"TEXT": span.text}]])
        for i, start, end in matcher(doc):
            mlen = end - start
            for j in range(start, end):
                if j not in idx2data:
                    continue
                catch_i, span = idx2data[j]
                if len(span) > mlen:
                    continue
                catch = catches[catch_i]
                catch["spans"].remove(span)
            if i in idx2data:
                continue
            span = doc[start:end]
            data = (i, span)
            for idx in range(start, end):
                idx2data[idx] = data
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
    return _preprocess_maps(source, stopwords)


def _preprocess_maps(source: Union[Doc, Span], stopwords: bool):
    idx2i = {}
    text_tokens = []
    curr_idx = 0
    for i, token in enumerate(source):
        idx2i[curr_idx] = i
        value = _get_token_text_norm(token, stopwords)
        value += token.whitespace_
        text_tokens.append(value)
        curr_idx += len(value)
    idx2i[curr_idx] = len(source)
    text = "".join(text_tokens)
    return idx2i, text.replace(" ", "_")


def _get_token_text_norm(token: Token, stopwords: bool):
    # if stopwords and (
    #     token.pos_
    #     in (
    #         "ADP",
    #         "ADV",
    #         "AUX",
    #         "CCONJ",
    #         "CONJ",
    #         "DET",
    #         "INTJ",
    #         "PART",
    #         "PUNCT",
    #         "PRON",
    #         "SCONJ",
    #         "SPACE",
    #         "X",
    #     )
    #     or (token.pos_ == "VERB" and token.tag_ != "VBG")
    # ):
    #     return "_"
    return token.lower_


def _span_idx2i(start_idx, end_idx, idx2i, maxlen):
    while start_idx not in idx2i and start_idx < maxlen:
        start_idx += 1
    while end_idx not in idx2i and end_idx < maxlen:
        end_idx += 1
    if start_idx == end_idx:
        end_i = idx2i[end_idx]
        return end_i - 1, end_i
    return idx2i[start_idx], idx2i[end_idx]


def _is_good_catch(page, catch):
    title = _remove_title_detailing(page["title"])
    pageup_count = sum(1 for c in title if c.isupper())
    catchup_count = sum(1 for c in catch if c.isupper())
    max_caps = catch.count("_") + 1
    diff = abs(pageup_count - catchup_count)
    return diff <= max_caps or diff >= len(catch) - max_caps
