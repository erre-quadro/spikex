from math import log, sqrt
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
        self.topicx = topicx or WikiTopicX(graph=graph, graph_name=graph_name)

    def __call__(
        self,
        docs: Iterable[Doc],
        correl_func: Callable = None,
        refresh: bool = None,
    ):
        docs_data = {}
        topics = set()
        iter_docs = (
            self.topicx(doc) if not doc._.topics or refresh else doc
            for doc in docs
        )
        for doc in iter_docs:
            doc_data = docs_data.setdefault(doc, {})
            for topic_id, count in doc._.topics:
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
    def inject_tfidf(data):
        for topic, tf in {**data}.items():
            if topic not in idfs:
                del data[topic]
                continue
            idf = idfs[topic]
            if not idf:
                idf = 1
            data[topic] = tf / idf

    linkage = {}
    idfs = {}
    for topics in docs_data.values():
        for topic in topics:
            if topic not in idfs:
                idfs[topic] = 0
            idfs[topic] += 1
    tot_docs = len(docs_data)
    idfs = {topic: log(tot_docs / freq) for topic, freq in idfs.items()}
    injected = set()
    for doc, data in docs_data.items():
        if doc not in injected:
            inject_tfidf(data)
            injected.add(doc)
        topics = set(data)
        if len(topics) == 0:
            continue
        doc_linkage = linkage.setdefault(doc, {})
        for other_doc, other_data in docs_data.items():
            if doc == other_doc or other_doc in doc_linkage:
                continue
            if other_doc not in injected:
                inject_tfidf(other_data)
                injected.add(other_doc)
            other_topics = set(other_data)
            common_topics = topics.intersection(other_topics)
            if len(other_topics) == 0 or len(common_topics) == 0:
                continue
            all_topics = topics.union(other_topics)
            # correlation by cosine similarity
            dotprod = sum(
                data.get(k, 0) * other_data.get(k, 0) for k in all_topics
            )
            maga = sqrt(sum(data.get(k, 0) ** 2 for k in all_topics))
            magb = sqrt(sum(other_data.get(k, 0) ** 2 for k in all_topics))
            correl = dotprod / (maga * magb)
            good_topics = [(t, data[t] + other_data[t]) for t in common_topics]
            good_topics.sort(key=lambda x: x[1], reverse=True)
            linkage_data = (correl, good_topics)
            doc_linkage.setdefault(other_doc, linkage_data)
            other_doc_linkage = linkage.setdefault(other_doc, {})
            other_doc_linkage.setdefault(doc, linkage_data)
        doc._.linkage = doc_linkage
