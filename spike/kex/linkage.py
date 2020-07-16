from typing import Callable, Iterable

from spacy.tokens import Doc

from ..wikigraph import WikiGraph
from .topics import WikiTopicX


class WikiLinkageX:
    def __init__(
        self,
        topicx: WikiTopicX = None,
        graph: WikiGraph = None,
        graph_name: str = None,
    ):
        Doc.set_extension("linkage", default={}, force=True)
        self._topicx = topicx or WikiTopicX(graph, graph_name)

    def __call__(
        self,
        docs: Iterable[Doc],
        correl_func: Callable = None,
        refresh: bool = None,
    ):
        docs_data = {}
        topics = set()
        iter_docs = (
            self._topicx(doc) if not doc._.topics or refresh else doc
            for doc in docs
        )
        for doc in iter_docs:
            doc_data = docs_data.setdefault(doc, {})
            for topic_id, count in doc._.topics.items():
                if topic_id not in doc_data:
                    doc_data[topic_id] = 0
                doc_data[topic_id] += count
                topics.add(topic_id)
        correl_func = (
            correl_func if correl_func is not None else _default_correl_func
        )
        correl_func(docs_data)
        return docs


def _default_correl_func(docs_data):
    linkage = {}
    for doc, data in docs_data.items():
        doc_linkage = linkage.setdefault(doc, {})
        for other_doc, other_data in docs_data.items():
            if doc == other_doc or other_doc in doc_linkage:
                continue
            topics = set([t for t in data if data[t] > 2])
            other_topics = set([t for t in other_data if other_data[t] > 2])
            common_topics = set.intersection(topics, other_topics)
            if (
                len(topics) == 0
                or len(other_topics) == 0
                or len(common_topics) == 0
            ):
                continue
            k1 = 0
            good_topics = {}
            for t in common_topics:
                k = (data.get(t, 0) + other_data.get(t, 0)) / 2
                good_topics.setdefault(t, k)
                k1 += k
            k2 = sum(
                (data.get(e, 0) + other_data.get(e, 0)) / 2 for e in topics
            )
            correl = k1 / k2
            good_topics = [
                (k, v)
                for k, v in sorted(
                    good_topics.items(), key=lambda x: x[1], reverse=True
                )
            ]
            linkage_data = (correl, good_topics)
            doc_linkage.setdefault(other_doc, linkage_data)
            other_doc_linkage = linkage.setdefault(other_doc, {})
            other_doc_linkage.setdefault(doc, linkage_data)
        doc._.linkage = doc_linkage
