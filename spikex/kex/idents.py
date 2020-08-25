from difflib import get_close_matches
from typing import Counter

from spacy.tokens import Doc

from .catches import WikiCatchX


class WikiIdentX(WikiCatchX):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        Doc.set_extension("idents", default=[], force=True)

    def __call__(self, doc: Doc):
        doc = super().__call__(doc)
        if doc._.idents and not self.refresh:
            return doc
        doc._.idents = self._get_idents(doc._.catches)
        return doc

    def _get_idents(self, catches):
        p2c = self._page2catch_r1(catches)
        p2c = self._page2catch_r2(catches, p2c)
        idents = [
            (span, page, score)
            for page, (catch, score) in p2c.items()
            for span in catch.spans
        ]
        return sorted(idents, key=lambda x: x[0].start)

    def _page2catch_r1(self, catches):
        page2catch = {}
        for catch in catches:
            t2p = {}
            disambi = False
            for page in catch.pages:
                hv = self.wg.get_head_vertex(page)
                if hv["disambi"]:
                    disambi = True
                    break
                v = self.wg.get_vertex(page)
                title = v["title"]
                if "_(" in title:
                    continue
                t2p[title] = page
            if disambi:
                continue
            ranker = Counter()
            titles = t2p.keys()
            for span in catch.spans:
                match = get_close_matches(span.text, titles, n=1, cutoff=0.2)
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

        ances_count = {}
        page2ances = {}
        for page, (catch, _) in page2catch.items():
            ances = self.wg.get_ancestors(page)
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
            best_page = None
            for page in catch.pages:
                hv = self.wg.get_head_vertex(page)
                if hv["disambi"]:
                    continue
                if page in new_pages:
                    best_page = page
                    best_score = new_pages[page][1]
                    continue
                common = ances.intersection(set(self.wg.get_ancestors(page)))
                if len(common) == 0:
                    continue
                score = page_score(ances_count, common)
                print(self.wg.get_vertex(page), "->", score)
                if score < 0.05:
                    continue
                rank.append((page, score))
            if not rank:
                continue
            rank.sort(key=lambda x: (x[1], -x[0]), reverse=True)
            page, score = rank[0]
            if page == best_page or score <= best_score:
                continue
            if best_page is not None:
                del new_pages[best_page]
            new_pages[page] = (catch, score)
        return new_pages
