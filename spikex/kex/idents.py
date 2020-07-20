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
            topic_pages.sort(key=lambda x: x[1], reverse=True)
            best_page = topic_pages[0]
            # if any(page[1] == best_page[1] for page in topic_pages[1:]):
            #     continue
            idents.extend(((span, best_page) for span in catch.spans))
        return sorted(idents, key=lambda x: x[0].start)

    def _get_topic_pages(self, topics, pages):
        topic_pages = []
        ents = set(topics)
        for page in pages:
            nbs = set(self.wg.get_neighborcats(page, large=True))
            common = set.intersection(ents, set(nbs))
            common_count = len(common)
            if common_count == 0:
                continue
            scores = [topics[e] for e in common]
            score = (min(scores) + max(scores)) / common_count
            topic_page = (page, score)
            topic_pages.append(topic_page)
        return topic_pages
