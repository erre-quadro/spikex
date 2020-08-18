from difflib import get_close_matches
from typing import Callable, Counter

from spacy.tokens import Doc

from ..wikigraph import WikiGraph
from .catches import WikiCatchX
from .topics import WikiTopicX


class WikiIdentX:
    def __init__(
        self,
        catchx: WikiCatchX = None,
        topicx: WikiTopicX = None,
        graph: WikiGraph = None,
        graph_name: str = None,
        refresh: bool = None,
        filter_span: Callable = None,
    ):
        Doc.set_extension("idents", default=[], force=True)
        self.topicx = topicx or WikiTopicX(
            graph=graph, graph_name=graph_name, refresh=refresh
        )
        self.catchx = catchx or self.topicx.catchx
        self.wg = self.topicx.wg
        self.refresh = refresh
        if filter_span:
            self.catchx.filter_span = filter_span

    def __call__(self, doc: Doc):
        if not doc._.catches or self.refresh:
            self.catchx(doc)
        # if not doc._.topics or self.refresh:
        #     self.topicx(doc)
        if not doc._.idents or self.refresh:
            # doc._.idents = self._get_idents(doc)
            doc._.idents = self._new_get_idents(doc._.catches)
        return doc

    def _new_get_idents(self, catches):
        pages = self._get_best_pages(catches)
        pages = self._get_better_pages_for_idents(pages, catches)
        idents = [
            (span, page, score)
            for page, (catch, score) in pages.items()
            for span in catch.spans
        ]
        return sorted(idents, key=lambda x: x[0].start)

    def _get_idents(self, doc):
        idents = []
        topics = doc._.topics
        for catch in doc._.catches:
            topic_pages = self._get_topic_pages(topics, catch.pages)
            if not topic_pages:
                continue
            topic_pages.sort(key=lambda x: x[1], reverse=True)
            best_page = topic_pages[0]
            idents.extend(((span, best_page) for span in catch.spans))
        return sorted(idents, key=lambda x: x[0].start)

    def _get_topic_pages(self, topics, pages):
        topic_pages = []
        ents = set(topics)
        for page in pages:
            nbs = set(self.wg.get_ancestors(page))
            common = set.intersection(ents, set(nbs))
            common_count = len(common)
            if common_count == 0:
                continue
            scores = [topics[e] for e in common]
            score = (min(scores) + max(scores)) / common_count
            topic_pages.append((page, score))
        return topic_pages

    def _get_best_pages(self, catches):
        pages = {}
        for catch in catches:
            t2p = {self.wg.get_vertex(p)["title"]: p for p in catch.pages}
            if any("(disambiguation)" in t for t in t2p.keys()):
                continue
            ranker = Counter()
            titles = [t for t in t2p if "_(" not in t]
            for span in catch.spans:
                m = get_close_matches(span.text, titles, n=1, cutoff=0.2)
                print(span, "->", m)
                if not m:
                    continue
                ranker.update([m[0]])
            if not ranker:
                continue
            rank = ranker.most_common(1)
            if not rank:
                continue
            title = rank[0][0]
            page = t2p[title]
            pages[page] = catch
        return pages

    def _get_better_pages_for_idents(self, pages, catches):
        def calc_page_score(cat2cnt, common):
            return sum(cat2cnt[c] for c in common) / len(cat2cnt)

        cat2cnt = {}
        page2ancs = {}
        for page, catch in pages.items():
            ancs = self.wg.get_ancestors(page)
            if not ancs:
                continue
            page2ancs[page] = ancs
            score = len(catch.spans)
            for anc in ancs:
                if anc not in cat2cnt:
                    cat2cnt[anc] = 0
                # if cat2cnt[anc] >= score:
                #     continue
                cat2cnt[anc] += score
        new_pages = {
            page: (catch, calc_page_score(cat2cnt, page2ancs[page]),)
            for page, catch in pages.items()
            if page in page2ancs
        }
        cats = set(cat2cnt.keys())
        for catch in catches:
            rank = []
            best_page = None
            best_score = 0
            for page in catch.pages:
                title = self.wg.get_vertex(page)["title"]
                if "(disambiguation)" in title:
                    continue
                if page in new_pages:
                    best_page = page
                    score = new_pages[page][1]
                    best_score = max(score, catch.score)
                    continue
                ancestors = set(self.wg.get_ancestors(page))
                common = cats.intersection(ancestors)
                if len(common) == 0:
                    continue
                score = calc_page_score(cat2cnt, common)
                if score < 0.05:
                    continue
                rank.append((page, score))
            if not rank:
                continue
            rank.sort(key=lambda x: x[1], reverse=True)
            for p, s in rank:
                print(self.wg.get_vertex(p)["title"], f"({s})")
            page, score = rank[0]
            if (
                page == best_page
                or score <= best_score
                or len([1 for el in rank if el[1] == score]) > 1
            ):
                if best_page is not None:
                    print(
                        "-> CONFIRM",
                        self.wg.get_vertex(best_page)["title"],
                        f"({best_score:.2f})",
                    )
                continue
            if best_page is not None:
                del new_pages[best_page]
                print(
                    "-> REPLACE:",
                    self.wg.get_vertex(best_page)["title"],
                    f"({best_score})",
                    "->",
                )
            print(
                "--> PICK",
                self.wg.get_vertex(page)["title"],
                f"({score:.2f} / {best_score:.2f})",
            )
            new_pages[page] = (catch, score)
        return new_pages
