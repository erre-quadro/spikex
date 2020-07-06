from collections import Counter
from typing import Iterable, Union

import regex as re
from cyac import Trie
from spacy.tokens import Doc, Span, Token

from ..wikigraph import WikiGraph
import numpy as np
from math import floor


class WikiClusterX:
    def __init__(self):
        self._leaves_map = {}
        self._trie_leaves_map = {}
        self._trie = Trie(ignore_case=True)
        self._wg = WikiGraph("respacy/data/enwiki_core_latest")
        trie_seen = set()
        for leaf in self._wg.leaves:
            title = leaf["title"]
            key = _normalize_title(title)
            if key not in self._leaves_map:
                self._leaves_map[key] = set()
            self._leaves_map[key].add(leaf.index)
            trie_text = key
            if trie_text in trie_seen:
                continue
            id_ = self._trie.insert(trie_text)
            self._trie_leaves_map[id_] = key
            trie_seen.add(trie_text)

    def __call__(self, docs: Iterable[Doc], threshold: float = None):
        docs_avg = {}
        docs_data = {}
        aggr_ents = set()
        for doc in docs:
            doc_data = docs_data.setdefault(doc, {})
            pp = docs[doc] in ("US4312338_A", "US2018160749_A1")
            pages_data = self._extract_pages_data(doc, pp)
            ents = self._get_cand_ents_new(pages_data, pp)
            # print(
            #     "#" * 20, docs[doc], "#" * 20, "\n",
            #     "\n".join(
            #         [
            #             self._wg.g.vs[e]["title"] + "/" + str(c)
            #             for e, c in sorted(ents.items(), key=lambda x: x[1], reverse=True)[:10]
            #         ]
            #     )
            # )
            for ent, count in ents.items():
                if ent not in doc_data:
                    doc_data[ent] = 0
                doc_data[ent] += count
                aggr_ents.add(ent)
        num_ents = len(aggr_ents)
        for doc, ents_data in docs_data.items():
            tot = sum(c for c in ents_data.values())
            docs_avg.setdefault(doc, tot / num_ents)
        linkage = {}
        for doc1, data1 in docs_data.items():
            l1 = linkage.setdefault(docs[doc1], {})
            for doc2, data2 in docs_data.items():
                if doc1 == doc2:
                    continue
                d1_set = set([e for e in data1 if data1[e] > 2])
                d2_set = set([e for e in data2 if data2[e] > 2])
                common = set.intersection(d1_set, d2_set)
                if len(d1_set) == 0 or len(d2_set) == 0 or len(common) == 0:
                    continue
                ents = d1_set | d2_set

                # good_ents = {}
                # for e in common:
                #     k = max(data1.get(e, 0), data2.get(e, 0))
                #     good_ents.setdefault(e, k)
                # k1 = sum(data1[e] for e in common)
                # k12 = sum(data1.values())
                # k2 = sum(data2[e] for e in common)
                # k22 = sum(data2.values())
                # k3 = (k1 / k12) + (k2 / k22)
                # correl = k3 / 2
                
                k1 = 0
                good_ents = {}
                for e in common:
                    k = (data1.get(e, 0) + data2.get(e, 0)) / 2
                    good_ents.setdefault(e, k)
                    k1 += k
                k2 = sum((data1.get(e, 0) + data2.get(e, 0)) / 2 for e in ents)
                correl = k1 / k2

                # k1 = sum(data1[e] for e in common)
                # k12 = sum(data1[e] for e in ents if e in data1)
                # k2 = sum(data2[e] for e in common)
                # k22 = sum(data2[e] for e in ents if e in data2)
                # k3 = (k1 / k12) + (k2 / k22)
                # correl = k3 / 2

                # correl = np.corrcoef(
                #     [data1.get(e, 0) for e in ents],
                #     [data2.get(e, 0) for e in ents]
                # )[0, 1]
                # if np.isnan(correl):
                #     correl = -1

                # print(
                #     docs[doc1],
                #     "-",
                #     docs[doc2],
                #     ":",
                #     correl,
                #     "|",
                #     len(common),
                #     "/",
                #     len(ents),
                #     "|",
                #     sum(data1[e] for e in common),
                #     f"({sum(data1[e] for e in common if data1[e] > 2)})",
                #     "/",
                #     sum(data1.values()),
                #     "|",
                #     sum(data2[e] for e in common),
                #     f"({sum(data2[e] for e in common if data2[e] > 2)})",
                #     "/",
                #     sum(data2.values()),
                # )
                # if (
                #     docs[doc1] == "US4312338_A"
                #     or docs[doc2] == "US4312338_A"
                # ) and (
                #     docs[doc1] == "US2018160749_A1"
                #     or docs[doc2] == "US2018160749_A1"
                # ):
                #     print(
                #         ", ".join(
                #             [
                #                 f"{self._wg.get_vertex(e)['title']} / {data1[e]} - {data2[e]}"
                #                 for e in common
                #             ]
                #         )
                #     )
                ents = [
                    (self._wg.get_vertex(e)["title"], c)
                    for e, c in sorted(
                        good_ents.items(), key=lambda x: x[1], reverse=True
                    )
                ]
                l1.setdefault(docs[doc2], (correl, ents))
        return linkage

    def _extract_pages_data(self, source: Union[Doc, Span], pp=None):
        idx2i, text = _preprocess(source, True)
        ac_sep = set([ord("_")])
        maxtlen = len(text)
        pages_data = {}
        for id_, start_idx, end_idx in self._trie.match_longest(text, ac_sep):
            start_i, end_i = _span_idx2i(start_idx, end_idx, idx2i, maxtlen)
            span = source[start_i:end_i]
            key = self._trie_leaves_map[id_]
            catch = text[start_idx:end_idx]
            if not _is_good_span_for_catch(span, catch):
                continue
            data = pages_data.setdefault(key, {})
            spans = data.setdefault("spans", [])
            spans.append(span)
            if "score" in data:
                data["freq"] += 1
                continue
            nfactor = 0
            rejects = set()
            data.setdefault("freq", 1)
            vertices = self._leaves_map[key]
            pages = data.setdefault("pages", {})
            for vertex in vertices:
                vx = self._wg.get_vertex(vertex)
                main_vx = self._wg.get_main_vertex(vx)
                if main_vx.index in pages or main_vx.index in rejects:
                    continue
                if not _is_good_ent_for_catch(vx, catch):
                    rejects.add(main_vx.index)
                    continue
                nfactor += 1
                pages.setdefault(main_vx.index)
            # if pp and nfactor == 1:
            #     print(
            #         "->",
            #         span,
            #         "-",
            #         ", ".join(
            #             [self._wg.get_vertex(e)["title"] for e in pages]
            #         ),
            #     )
            span_score = (1 / nfactor) if nfactor else 0
            data.setdefault("score", span_score)
        return pages_data.values()

    def _get_cand_ents_new(self, pages_data, pp=None):
        freqs = {}
        score_th = 0.10
        curr_score = 1.0
        cand_ents = set()
        counter = Counter()
        while curr_score >= score_th:
            layer_ents = []
            for data in pages_data:
                if data["score"] != curr_score:
                    continue
                pages = data["pages"]
                vertices = list(pages)
                nbcs = self._wg.get_neighborcats(vertices, large=True)
                for v, nb in zip(vertices, nbcs):
                    # if pp:
                    #     print(self._wg.get_vertex(v)["title"])
                    for e in nb:
                        freqs.setdefault(e, data["freq"]) 
                        layer_ents.append(e)
            curr_score /= 2
            counter.update(
                [e for e in layer_ents if len(cand_ents) == 0 or e in cand_ents]
            )
            most_common = counter.most_common()
            if not most_common:
                continue
            best = most_common[0]
            best_count = best[1]
            for e, c in most_common:
                if c >= best_count * curr_score / 2:
                    continue
                del counter[e]
            cand_ents.update(counter)
        return {e: c * floor(freqs[e] ** 0.75) for e, c in counter.items()}


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


def _is_good_span_for_catch(span, catch):
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
    last = span[-1]
    bad_pos = ("ADP", "DET", "CONJ", "CCONJ", "SCONJ", "NUM")
    if any(token.pos_ in bad_pos for token in span):
        return
    return any(
        token.pos_ in good_pos or token.tag_ in good_tag for token in span
    )


def _is_good_ent_for_catch(ent, catch):
    ent_title = _remove_title_detailing(ent["title"])
    entup_count = sum(1 for c in ent_title if c.isupper())
    catchup_count = sum(1 for c in catch if c.isupper())
    max_caps = catch.count("_") + 1
    diff = abs(entup_count - catchup_count)
    return diff <= max_caps or diff >= len(catch) - max_caps
