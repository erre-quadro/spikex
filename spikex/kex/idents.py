from dataclasses import dataclass
from difflib import get_close_matches
from typing import Counter

from spacy.tokens import Doc, Span

from .catches import WikiCatchX


@dataclass
class Ident:
    page: int
    score: float
    span: Span


class WikiIdentX(WikiCatchX):
    def __init__(self, *args, **kwargs):
        if "filter_span" not in kwargs:
            kwargs["filter_span"] = lambda x: (
                any(
                    t.pos_ in ("NOUN", "PROPN") or t.tag_ in ("VBG",)
                    for t in x
                )
            )
        super().__init__(*args, **kwargs)
        Doc.set_extension("idents", default=[], force=True)

    def __call__(self, doc: Doc):
        doc = super().__call__(doc)
        p2c = self._page2catch_r1(doc._.catches)
        p2c = self._page2catch_r2(doc._.catches, p2c)
        doc._.idents = self._get_best_idents(p2c)
        for ident in doc._.idents:
            print(self.wg.get_vertex(ident.page)["title"], "->", ident.score)
        return doc

    def _page2catch_r1(self, catches):
        page2catch = {}
        for catch in catches:
            t2p = {}
            for page in catch.pages:
                print(self.wg.get_vertex(page)["title"])
                hv = self.wg.get_head_vertex(page)
                if hv["disambi"]:
                    continue
                v = self.wg.get_vertex(page)
                title = v["title"]
                if "_(" in title:
                    continue
                t2p[title] = page
            ranker = Counter()
            titles = t2p.keys()
            for span in catch.spans:
                match = get_close_matches(span.text, titles, n=1, cutoff=0.3)
                if not match:
                    continue
                ranker.update([match[0]])
            if not ranker:
                continue
            t = ranker.most_common(1)[0][0]
            page2catch[t2p[t]] = (catch, 1)
        return page2catch

    def _page2catch_r2(self, catches, page2catch):
        def page_score(counts, common):
            return sum(counts[c] for c in common) / len(counts)

        page2ances = {}
        ances_count = {}
        for page, (catch, _) in page2catch.items():
            ances = self.wg.get_ancestor_vertices(page)
            if not ances:
                continue
            page2ances[page] = ances
            count = len(catch.spans)
            for ance in ances:
                if ance not in ances_count:
                    ances_count[ance] = 0
                ances_count[ance] += count
        new_pages = {
            page: (catch, page_score(ances_count, page2ances[page]))
            for page, (catch, _) in page2catch.items()
            if page in page2ances
        }
        ances = set(ances_count.keys())
        for catch in catches:
            rank = []
            best_score = 0
            # pages = set()
            # for page in catch.pages:
            #     hv = self.wg.get_head_vertex(page)
            #     if not hv["disambi"]:
            #         pages.add(page)
            #         continue
            #     pages.update(
            #         [v.index for v in self.wg.get_disambi_vertices(hv)]
            #     )
            for page in catch.pages:
                hv = self.wg.get_head_vertex(page)
                if hv["disambi"]:
                    continue
                if page in new_pages:
                    best_score = new_pages[page][1]
                    continue
                page_ances = set(self.wg.get_ancestor_vertices(page))
                common = set.intersection(ances, page_ances)
                if len(common) == 0:
                    continue
                score = page_score(ances_count, common)
                rank.append((page, score))
            if not rank:
                continue
            rank.sort(key=lambda x: (x[1], -x[0]), reverse=True)
            page, score = rank[0]
            if score < best_score:
                continue
            new_pages[page] = (catch, score)
        return new_pages

    def _get_best_idents(self, page2catch):
        idents = sorted(
            [
                Ident(page=page, score=score, span=span)
                for page, (catch, score) in page2catch.items()
                for span in catch.spans
                if score >= 0.02
            ],
            key=lambda x: (x.span.start, -x.span.end),
        )
        last = None
        good_idents = []
        for i, ident in enumerate(idents):
            if not last or ident.span.start >= last.span.end:
                good_idents.append(ident)
                last = ident
            else:
                ident_nounness = _get_nounness(ident.span)
                last_nounness = _get_nounness(last.span)
                if (
                    ident_nounness > last_nounness
                    or ident_nounness == last_nounness
                    and ident.score > last.score
                ):
                    good_idents.remove(last)
                    for idx in range(idents.index(last) + 1, i):
                        good_idents.append(idents[idx])
                    good_idents.append(ident)
                    last = ident
        return good_idents


def _get_nounness(span: Span):
    return sum(
        token.pos_ in ("ADJ", "NOUN", "PROPN") or token.tag_ in ("VBG",)
        for token in span
    )
