from collections import Counter
from itertools import chain
from typing import Union

import regex as re
from cyac import Trie
from spacy.tokens import Doc, Span, Token

from ..matcher import Matcher
from ..wikigraph import WikiGraph

__all__ = ["WikiEntX"]


class WikiEntX:
    def __init__(self):
        Doc.set_extension("wiki_chunks", default=[], force=True)
        Span.set_extension("wiki_ents", default=[], force=True)
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

    def __call__(self, source: Union[Doc, Span], stopwords=None):
        pages_data = self._extract_pages_data(source, stopwords)
        cand_ents = self._get_cand_ents_new(pages_data)
        if not cand_ents:
            return source
        # _expand_cand_ents(cand_ents, pages_data)
        # print(
        #     "\n".join(
        #         [
        #             self._wg.g.vs[e]["title"] + "/" + str(c)
        #             for e, c in sorted(cand_ents.items(), key=lambda x: x[1])
        #         ]
        #     )
        # )
        doc = source if isinstance(source, Doc) else source.doc
        chunks = []
        for data in pages_data:
            pages = data["pages"]
            matching_pages = self._get_matching_pages(cand_ents, pages)
            ents = [
                (
                    self._wg.get_vertex(v),
                    [
                        self._wg.get_vertex(e) for e in es
                    ],  # if e in pages[v][0]],
                    s,
                )
                for v, es, s in matching_pages
                if s > 0.01
            ]
            if not ents:
                continue
            # print(
            #     "\n".join(
            #         [
            #             v["title"] + "/" + str(s)
            #             for v, e, s in ents
            #         ]
            #     )
            # )
            ents.sort(key=lambda x: x[2], reverse=True)
            for span in data["spans"]:
                chunks.append((span, [ents[0]]))
        key2ents = {}
        matcher = Matcher(doc.vocab)
        chunks.sort(key=lambda x: len(x[0]), reverse=True)
        for chunk, ents in chunks:
            key2ents.setdefault(chunk.text, ents)
            matcher.add(chunk.text, [[{"TEXT": chunk.text}]])
        seen = set()
        for kid, start, end in matcher(doc):
            indexes = range(start, end)
            if any(i in seen for i in indexes):
                continue
            seen.update(indexes)
            span = doc[start:end]
            key = doc.vocab.strings[kid]
            span._.wiki_ents = key2ents[key]
            doc._.wiki_chunks.append(span)
        doc._.wiki_chunks.sort(key=lambda x: x.start)
        return source

    def _extract_pages_data(self, source: Union[Doc, Span], stopwords=None):
        idx2i, text = _preprocess(source, stopwords)
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
                continue
            nfactor = 0
            rejects = set()
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
                pages.setdefault(vx.index, [])
            # nbh = self._wg.get_neighborcats(pages)
            # for page, nb in zip(pages, nbh):
            #     nbc = self._wg.get_neighborcats(nb, large=True)
            #     pages[page] = (set(nb), set(chain.from_iterable(nbc)))
            span_score = (1 / nfactor) if nfactor else 0
            data.setdefault("score", span_score)
        return pages_data.values()

    def _get_cand_ents(self, pages_data):
        seeds = [
            nbs[0]
            for data in pages_data
            if data["score"] >= 1
            for nbs in data["pages"].values()
        ]
        # counter = Counter()
        # for seed in seeds:
        #     counter.update(seed)
        # return {e: c for e, c in counter.most_common()}
        refs = {}
        # most_common = {e: c for e, c in counter.most_common()}
        # vertices = list(most_common.keys())
        vertices = list(chain.from_iterable(seeds))
        for i, nbh in enumerate(seeds):
            e = vertices[i]
            for nb in nbh:
                refs_nb = refs.setdefault(nb, [])
                refs_nb.append(e)
                refs_e = refs.setdefault(e, [])
                refs_e.append(nb)
        cands = set()
        for el, cn in zip(
            vertices, self._wg.g.similarity_dice(vertices=vertices)
        ):
            good = [
                vertices[i]
                for i, e in enumerate(cn)
                if e > 0.01
                and vertices[i] != el
                and el not in refs[vertices[i]]
                and vertices[i] not in refs[el]
            ]
            cands.update(good)
        return {e: 1 for e in cands}

    def _get_cand_ents_new(self, pages_data):
        score_th = 0.25
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
                    if not pages[v]:
                        pages[v].extend(nb)
                    if len(cand_ents) == 0:
                        layer_ents.extend(nb)
                        continue
                    common = set.intersection(cand_ents, set(nb))
                    if len(common) == 0:
                        continue
                    layer_ents.extend(nb)
            curr_score /= 2
            counter.update(
                layer_ents
                if len(cand_ents) == 0
                else [e for e in layer_ents if e in cand_ents]
            )
            most_common = counter.most_common()
            if not most_common:
                continue
            best = most_common[0]
            best_count = best[1]
            for e, c in most_common:
                if c >= best_count * curr_score / 3:
                    continue
                del counter[e]
            nbcs = self._wg.get_neighborcats(counter)
            counter.update(chain.from_iterable(nbcs))
            cand_ents.update(counter)
        return counter

        #     if all(c == 1 for c in counter.values()):
        #         cand_ents.update(layer_ents)
        #         continue
        #     # good_ents = set()
        #     for e, c in {**counter}.items():
        #         if c > 1:
        #             # if e not in ents_seen:
        #             # good_ents.add(e)
        #             continue
        #         del counter[e]
        #         if e not in cand_ents:
        #             continue
        #         cand_ents.remove(e)
        #     # nbcs = self._wg.get_neighborcats(good_ents)
        #     # counter.update(chain.from_iterable(nbcs))
        #     # cand_ents.update(counter)
        # return {e: c for e, c in counter.most_common() if c > 1}

    def _get_matching_pages(self, cand_ents, pages):
        matching_pages = []
        ents = set(cand_ents)
        for v, nbs in pages.items():
            nbs_set = set(nbs or self._wg.get_neighborcats(v, large=True)[0])
            common = set.intersection(ents, set(nbs_set))
            common_count = len(common)
            if common_count == 0:
                continue
            # score = max(cand_ents[e] for e in common)  # sum(cand_ents[e] for e in common) / len(nbs_set) ** 0.8
            # score = sum(cand_ents[e] for e in common) * common_count / len(nbs_set) ** 0.8
            score = common_count / len(nbs_set) ** 0.8
            matching_page = (v, common, score)
            matching_pages.append(matching_page)
        counts = cand_ents.values()
        emin = min(counts)
        emax = max(counts)
        # for mp in sorted(matching_pages, key=lambda x: x[2], reverse=True):
        #     print("==>", self._wg.get_vertex(mp[0])["title"], "-", mp[2], ":", len(mp[1]), " - avg:", (emin+emax)/2)
        return matching_pages


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
    bad_pos = ("ADP", "DET", "CONJ", "CCONJ", "SCONJ")
    if first.pos_ in bad_pos or last.pos_ in bad_pos:
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


def _expand_cand_ents(cand_ents, pages_data):
    for data in pages_data:
        for _, ents, score in _get_matching_pages(cand_ents, data["pages"]):
            if score < 0.8:
                continue
            cand_ents.update({e: 1 for e in ents})
    return cand_ents


def _get_matching_pages(cand_ents, pages):
    matching_pages = []
    ents = set(cand_ents)
    for v, nbs in pages.items():
        nb = nbs[1]
        common = set.intersection(ents, nb)
        common_count = len(common)
        if common_count == 0:
            continue
        # print(
        #     ", ".join([self._wg.get_vertex(c)["title"] for c in common])
        # )
        # ntotal = len(nb)
        # nsimil = len(common)
        # k1 = 1 / nsimil
        # k2 = 1 / ntotal
        # k3 = nsimil + 1 - k1 + 1 - k2
        # score = k3 / ntotal ** 0.8
        # score = sum(cand_ents[c] for c in common) / len(nb) ** 0.8
        score = common_count / len(nb) ** 0.8
        matching_page = (v, nb, score)
        matching_pages.append(matching_page)
    return matching_pages
