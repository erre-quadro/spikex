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
    ):
        Doc.set_extension("idents", default=[], force=True)
        self._topicx = topicx or WikiTopicX(graph, graph_name, refresh)
        self._catchx = catchx or WikiCatchX(self._topicx.wg)
        self.wg = self._topicx.wg
        self.refresh = refresh

    def __call__(self, doc: Doc):
        if not doc._.catches or self._refresh:
            self._catchx(doc)
        if not doc._.topics or self._refresh:
            self._topicx(doc)
        if not doc._.idents or self._refresh:
            doc._.idents = self._get_idents(doc)
        return doc

    def _get_idents(self, doc):
        idents = []
        topics = doc._.topics
        for catch in doc._.catches:
            topic_pages = self._get_topic_pages(topics, catch.pages)
            if not topic_pages:
                continue
            topic_pages.sort(key=lambda x: x[2], reverse=True)
            idents.extend(((span, [topic_pages[0]]) for span in catch.spans))
        return sorted(idents, key=lambda x: x.start)

    def _get_topic_pages(self, topics, pages):
        topic_pages = []
        ents = set(topics)
        for v, nbs in pages.items():
            nbs_set = set(nbs or self.wg.get_neighborcats(v, large=True)[0])
            common = set.intersection(ents, set(nbs_set))
            common_count = len(common)
            if common_count == 0:
                continue
            # score = max(cand_ents[e] for e in common)  # sum(cand_ents[e] for e in common) / len(nbs_set) ** 0.8
            # score = sum(cand_ents[e] for e in common) * common_count / len(nbs_set) ** 0.8
            score = common_count / len(nbs_set) ** 0.8
            if score < 0.01:
                continue
            topic_page = (v, score)
            topic_pages.append(topic_page)
        # counts = topics.values()
        # emin = min(counts)
        # emax = max(counts)
        # for mp in sorted(matching_pages, key=lambda x: x[2], reverse=True):
        #     print("==>", self._wg.get_vertex(mp[0])["title"], "-", mp[2], ":", len(mp[1]), " - avg:", (emin+emax)/2)
        return topic_pages
