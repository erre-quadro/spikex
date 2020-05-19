from itertools import combinations

import regex as re
from cyac import Trie
from spacy.tokens import Doc, Span

from ..util import span_idx2i
from ..wikigraph import WikiGraph


class WikiEntX:
    def __init__(self):
        Doc.set_extension("wiki_chunks", default=[], force=True)
        Doc.set_extension("wiki_chunks_ctx", default=[], force=True)
        Span.set_extension("wiki_ents", default=[], force=True)
        Span.set_extension("wiki_labels", default=[], force=True)
        self._ents_map = {}
        self._ents_id_map = {}
        self._wikigraph = WikiGraph(version="core_latest")
        self._trie = Trie(ignore_case=True)
        for vx in self._wikigraph.leaves:
            ent = self._wikigraph.get_title(vx)
            if not ent:
                continue
            key_ent = _fix_ent(ent)
            if key_ent not in self._ents_map:
                self._ents_map[key_ent] = []
            ents = self._ents_map[key_ent]
            if vx not in ents:
                ents.append(vx)
            if key_ent not in self._trie:
                id_ = self._trie.insert(key_ent)
                self._ents_id_map[id_] = key_ent

    def __call__(self, doc: Doc):
        sep = "_"
        text = doc.text.replace(" ", sep)
        ac_sep = set([ord(sep)])
        wiki_chunks = set()
        doc_maxlen = len(doc.text)
        for id_, start, end in self._trie.match_longest(text, ac_sep):
            key_ent = self._ents_id_map[id_]
            ents = self._ents_map[key_ent]
            ent_score = 1 / len(ents)
            for vx in ents:
                s, e = span_idx2i(doc, start, end, doc_maxlen)
                span = doc[s:e]
                if not _is_good_entity(span):
                    continue
                parents = self._wikigraph.get_parents(vx)
                if not parents:
                    continue
                span._.wiki_labels.append((vx, set(parents), ent_score))
                doc._.wiki_chunks.append(span)
                # chunks = wiki_chunks.setdefault(span.sent, set())
                wiki_chunks.add((key_ent, span))
        res = []
        # for sent, chunks in wiki_chunks.items():
        for c1, c2 in combinations(wiki_chunks, 2):
            if c1[0] == c2[0]:
                continue
            for l1 in c1[1]._.wiki_labels:
                for l2 in c2[1]._.wiki_labels:
                    if self._wikigraph.are_redirects(l1[0], l2[0]):
                        continue
                    # l1_ps = self._wikigraph.get_parents(l1[0])
                    # if not l1_ps:
                    #     continue
                    # l2_ps = self._wikigraph.get_parents(l2[0])
                    # if not l2_ps:
                    #     continue
                    # for l1_p in {*l1_ps}:
                    #     l1_ps.extend(self._wikigraph.get_parents(l1_p))
                    # for l2_p in {*l2_ps}:
                    #     l2_ps.extend(self._wikigraph.get_parents(l2_p))
                    common = set.intersection(l1[1], l2[1])
                    if len(common) == 0:
                        continue
                    # r = res.setdefault(sent, [])
                    res.append((l1, l2, common))

        score_f = lambda x: (x[0][2] + x[1][2]) / 2
        rank = sorted(
            [
                (l1, l2, common, score_f((l1, l2)))
                # for r in res
                for l1, l2, common in res
            ],
            key=lambda x: x[3],
            reverse=True,
        )

        good_ents = set()
        for l1, l2, common, score in rank:
            if score != 1.0:
                break
            print(
                score,
                ":",
                self._wikigraph.get_title(l1[0]),
                "-",
                self._wikigraph.get_title(l2[0]),
                ":",
                ", ".join([self._wikigraph.get_title(el) for el in common]),
            )
            for l in (l1, l2):
                # print(
                #     self._wikigraph.get_title(l[0]),
                #     ", ".join([self._wikigraph.get_title(el) for el in l[1]])
                # )
                good_ents.update(
                    [
                        child
                        for ent in l[1]
                        # for parent in self._wikigraph.get_parents(ent)
                        for child in self._wikigraph.get_children(ent)
                    ]
                )

        wiki_chunks = []
        for span in doc._.wiki_chunks:
            wl = []
            for label in span._.wiki_labels:
                ents = set.intersection(good_ents, label[1])
                if len(ents) == 0:
                    continue
                vx = label[0]
                vxt = self._wikigraph.get_title(vx)
                if not vxt:
                    continue
                wl.append((vx, vxt, label[1]))
            if not wl:
                continue
            span._.wiki_labels = wl
            wiki_chunks.append(span)
        doc._.wiki_chunks = wiki_chunks

        fd = open("log", "w+")
        for span in doc._.wiki_chunks:
            fd.write(f"{span.text}\n")
            for l in span._.wiki_labels:
                fd.write(
                    f"\t{l[1]} - {', '.join([self._wikigraph.get_title(el) for el in l[2]])}\n"
                )


_XP_FIX_ENT = re.compile(r"_\(.+\)")


def _fix_ent(ent):
    return _XP_FIX_ENT.sub("", ent).lower()


def _is_good_entity(span):
    first = span[0]
    if (
        len(span) == 1
        and first.tag_ not in ("VBG")
        and (first.pos_ not in ("NOUN", "PROPN") or first.pos_ in ("AUX"))
    ):
        return False
    last = span[-1]
    if (
        first.pos_ in ("ADP", "DET", "CONJ", "CCONJ", "SCONJ") 
        or last.pos_ in ("ADP", "DET", "CONJ", "CCONJ", "SCONJ")
    ):
        return False
    return any(token.pos_ in ("NOUN", "PROPN", "VERB") for token in span)
