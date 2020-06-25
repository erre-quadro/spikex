from typing import Iterable

from spacy.tokens import Doc

from ..entity_linking.wikientx import WikiEntX


class WikiCluster:
    def __init__(self):
        self._wex = WikiEntX()

    def __call__(self, docs: Iterable[Doc], threshold: float = None):
        docs_avg = {}
        docs_data = {}
        for doc in (self._wex(doc) for doc in docs):
            tot = 0
            doc_data = docs_data.setdefault(doc, {})
            for chunk in doc._.wiki_chunks:
                for _, ents, _ in chunk._.wiki_ents:
                    for ent in ents:
                        if ent not in doc_data:
                            doc_data[ent] = 0
                        doc_data[ent] += 1
                        tot += 1
            avg = 0 if len(doc_data) == 0 else tot / len(doc_data)
            docs_avg.setdefault(doc, avg)
        th = threshold or 0.5
        linkage = {}
        for doc1, data1 in docs_data.items():
            l1 = linkage.setdefault(doc1, {})
            for doc2, data2 in docs_data.items():
                if doc1 == doc2:
                    continue
                els = []
                for ent, c1 in data1.items():
                    c2 = data2[ent] if ent in data2 else 0
                    e1 = c1 - docs_avg[doc1]
                    e2 = c2 - docs_avg[doc2]
                    els.append((e1 * e2, e1 ** 2, e2 ** 2))
                if not els:
                    continue
                k1 = sum([e[0] for e in els])
                k2 = sum([e[1] for e in els])
                k3 = sum([e[2] for e in els])
                if k2 == 0 or k3 == 0:
                    continue
                correl = k1 / (k2 * k3) ** 0.5
                # if correl < th:
                #     continue
                l1.setdefault(doc2, correl)
        return linkage
        seen = set()
        clusters = []
        for el1, mts in linkage.items():
            cluster = set([el1])
            adding = set(mts)
            while adding and len(adding) > 0:
                el2 = adding.pop()
                if el2 in seen:
                    continue
                seen.add(el2)
                cluster.add(el2)
                if el2 not in linkage:
                    continue
                adding.update(linkage[el2])
            clusters.append(cluster)
        singles = [{d} for d in set.difference(set(docs), seen)]
        return clusters + singles
