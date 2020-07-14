from collections import Counter
from math import floor

from spacy.tokens import Doc

from ..wikigraph import WikiGraph
from .catches import WikiCatchX

MIN_SCORE_THRESHOLD = 0.05


class WikiTopicX:
    def __init__(
        self,
        catchx: WikiCatchX = None,
        graph: WikiGraph = None,
        graph_name: str = None,
        refresh: bool = None,
    ):
        Doc.set_extension("topics", default={}, force=True)
        self._catchx = catchx or WikiCatchX(graph, graph_name)
        self.wg = self._catchx.wg
        self.refresh = refresh

    def __call__(self, doc: Doc):
        if not doc._.catches or self._refresh:
            self._catchx.min_score = MIN_SCORE_THRESHOLD
            self._catchx(doc)
        if not doc._.topics or self._refresh:
            doc._.topics = self._get_topics(doc._.catches)
        return doc

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
                freq = len(catch.spans)
                catch_score = catch.score
                nbcs = self.wg.get_neighborcats(catch.pages, large=True)
                for nb in nbcs:
                    for e in nb:
                        freqs.setdefault(e, freq)
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
        return {e: c * floor(freqs[e] ** 0.75) for e, c in topics.items()}
