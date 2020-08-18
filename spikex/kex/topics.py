from collections import Counter
from difflib import get_close_matches
from math import floor

from spacy.tokens import Doc

from ..wikigraph import WikiGraph
from .catches import WikiCatchX

MIN_SCORE_THRESHOLD = 0.10


class WikiTopicX:
    def __init__(
        self,
        catchx: WikiCatchX = None,
        graph: WikiGraph = None,
        graph_name: str = None,
        refresh: bool = None,
    ):
        Doc.set_extension("topics", default={}, force=True)
        self.catchx = catchx or WikiCatchX(graph=graph, graph_name=graph_name)
        self.wg = self.catchx.wg
        self.refresh = refresh

    def __call__(self, doc: Doc):
        if not doc._.catches or self.refresh:
            self.catchx.min_score = MIN_SCORE_THRESHOLD
            self.catchx(doc)
        if not doc._.topics or self.refresh:
            doc._.topics = self._new_get_topics(doc._.catches)
        return doc

    def _new_get_topics(self, catches):
        topics = {}
        for catch in catches:
            should_skip = False
            title2page = {
                self.wg.get_vertex(p)["title"]: p for p in catch.pages
            }
            for title in title2page.keys():
                if "disambiguation" in title:
                    should_skip = True
                    break
            if should_skip:
                continue
            ranker = Counter()
            for span in catch.spans:
                m = get_close_matches(span.text, title2page.keys(), n=1)
                if not m:
                    continue
                ranker.update([m[0]])
            if not ranker:
                continue
            rank = ranker.most_common(1)
            if not rank:
                continue
            title = rank[0][0]
            page = title2page[title]
            cats = self.wg.get_ancestors(page)
            tot_occurs = len(catch.spans)
            for cat in cats:
                if cat not in topics:
                    topics[cat] = 0
                topics[cat] += tot_occurs
        good_topics = {}
        total_spans = sum(len(catch.spans) for catch in catches)
        for e, c in topics.items():
            score = c / total_spans
            good_topics[e] = score
        return good_topics

    def _get_topics(self, catches):
        freqs = {}
        curr_score = 1.0
        exhausted = False
        topics = Counter()
        score_th = MIN_SCORE_THRESHOLD
        iter_catches = iter(
            sorted(catches, key=lambda x: x.score, reverse=True)
        )
        while curr_score >= score_th and not exhausted:
            layer_ents = []
            catch_score = curr_score
            while catch_score == curr_score:
                catch = next(iter_catches, None)
                if not catch:
                    exhausted = True
                    break
                count = len(catch.spans)
                catch_score = catch.score
                for nb in self.wg.get_neighborcats(catch.pages, large=True):
                    for e in nb:
                        if e not in freqs:
                            freqs[e] = 0
                        freqs[e] += count
                        layer_ents.append(e)
            curr_score /= 2
            topics.update([e for e in layer_ents if not topics or e in topics])
            most_common = topics.most_common()
            if not most_common:
                continue
            best = most_common[0]
            best_count = best[1]
            for e, c in most_common:
                if c >= best_count * curr_score / 2:
                    continue
                del topics[e]
        total_spans = sum(len(catch.spans) for catch in catches)
        good_topics = {}
        for e, c in topics.items():
            count = floor(c / total_spans)
            good_topics[e] = count
        return good_topics
