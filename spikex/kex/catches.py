from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Union

from spacy.tokens import Doc, Span

from ..wikigraph import WikiGraph


@dataclass
class Catch:
    pages: tuple
    spans: tuple


class WikiCatchX:
    def __init__(
        self,
        graph: Union[WikiGraph, Path, str],
        filter_span: Callable = None,
        ignore_case: bool = None,
    ):
        self.wg = (
            graph if isinstance(graph, WikiGraph) else WikiGraph.load(graph)
        )
        self.filter_span = filter_span or (lambda x: True)
        self.ignore_case = ignore_case
        Doc.set_extension("catches", default=[], force=True)

    def __call__(self, doc: Doc):
        catch_data = {}
        idx2i, text = _preprocess(doc)
        maxtlen = len(text)
        for start_idx, end_idx, pages in self.wg.find_all_pages(
            text, self.ignore_case
        ):
            start_i, end_i = _span_idx2i(start_idx, end_idx, idx2i, maxtlen)
            if start_i >= end_i:
                continue
            span = doc[start_i:end_i]
            if not self.filter_span(span):
                continue
            key = span.lower_
            data = catch_data.setdefault(key, {})
            data.setdefault("pages", pages)
            spans = data.setdefault("spans", set())
            spans.add(span)
        catches = list(catch_data.values())
        # self._fix_catches(catches, doc)
        doc._.catches = [
            Catch(pages=tuple(catch["pages"]), spans=tuple(catch["spans"]))
            for catch in catches
        ]
        return doc

    def _fix_catches(self, catches, doc):
        idx2data = {}
        # matcher = Matcher(doc.vocab)
        # for i, catch in enumerate(catches):
        #     for span in catch["spans"]:
        #         pattern = [
        #             {"LEMMA": token.lemma_}
        #             if token.pos_ in ("NOUN",)
        #             else {"TEXT": token.text}
        #             for token in span
        #         ]
        #         matcher.add(i, [pattern])
        empty_catches = []
        for i, catch in enumerate(catches):
            for j, span in enumerate(catch["spans"]):
                # for i, start, end in matcher(doc):
                # span = doc[start:end]
                if not self.filter_span(span):
                    continue
                # mlen = end - start
                mlen = len(span)
                should_stop = False
                for k in range(span.start, span.end):  # start, end):
                    if k not in idx2data:
                        continue
                    catch_i, old_span = idx2data[k]
                    if len(old_span) > mlen:
                        should_stop = True
                        break
                    catch = catches[catch_i]
                    if old_span not in catch["spans"]:
                        continue
                    del idx2data[k]
                    catch["spans"].remove(old_span)
                    if not catch["spans"]:
                        empty_catches.append(catch)
                if should_stop:
                    break
                data = (i + j, span)
                for idx in range(span.start, span.end):
                    idx2data[idx] = data
                catch = catches[data[0]]
                catch["spans"].add(span)
                if catch in empty_catches:
                    empty_catches.remove(catch)
        for catch in empty_catches:
            catches.remove(catch)
        return catches


def _preprocess(source: Union[Doc, Span]):
    idx2i = {}
    text_tokens = []
    curr_idx = 0
    for i, token in enumerate(source):
        idx2i[curr_idx] = i
        value = token.lemma_ if token.pos_ == "NOUN" else token.text
        value += token.whitespace_
        text_tokens.append(value)
        curr_idx += len(value)
    idx2i[curr_idx] = len(source)
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
