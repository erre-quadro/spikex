from collections import Counter
from itertools import combinations

import numpy as np
from gensim.models import KeyedVectors
from spacy.tokens import Doc


class ClusterX:
    def __init__(self, min_score):
        Doc.set_extension("cluster_chunks", default=[])
        self.min_score = min_score

    def __call__(self, doc):
        doc._.cluster_chunks = cluster_chunks(
            list(doc.noun_chunks), min_score=self.min_score
        )
        return doc


def cluster_chunks(chunks, stopwords=False, filter_pos=None, min_score=None):
    key2index, key2vector = _map_key_to_vector(chunks, stopwords, filter_pos)
    if not key2index or not key2vector:
        return
    model = KeyedVectors(chunks[0].vector.size)
    keys = list(key2vector.keys())
    weights = list(key2vector.values())
    model.add(keys, weights)
    clusters = cluster_balls_multi(model, keys, min_score=min_score)
    return [[chunks[key2index[i]] for i in cluster] for cluster in clusters]


def cluster_balls(model, root, max_size=None, min_score=None):
    if root not in model:
        return
    max_size = max_size or 30
    neighs = model.most_similar(root, topn=max_size)
    if not neighs:
        return
    if min_score is None:
        mean = _get_neighs_mean_score(model, neighs)
        min_score = mean - 0.05
    cut_off = 0.5
    clusters = []
    root_cluster = {root}
    seen = {root: (root_cluster, 1)}
    for n, s in neighs:
        if s <= cut_off:
            break
        if n in seen:
            continue
        if s >= min_score:
            root_cluster.add(n)
            seen.setdefault(n, (root_cluster, s))
            continue
        cluster = set()
        min_sub_score = min_score + 0.05
        for nn, ss in model.most_similar(n, topn=max_size):
            if ss <= cut_off:
                break
            if nn in seen:
                c, b = seen[nn]
                if c == root_cluster or b >= ss:
                    continue
            if ss >= min_sub_score:
                if nn in seen:
                    prev_cluster = seen[nn][0]
                    prev_cluster.remove(nn)
                cluster.add(nn)
                seen[nn] = (cluster, ss)
        cluster.add(n)
        seen.setdefault(n, (cluster, 1))
        clusters.append(cluster)
        if len(cluster) < 3:
            continue
        intruder = _get_intruder(model, cluster)
        if intruder is None:
            continue
        del seen[intruder]
        cluster.remove(intruder)
    clusters.insert(0, root_cluster)
    return clusters


def cluster_balls_multi(model, keys, max_size=None, min_score=None):
    clusters = []
    for key in keys:
        for ball in cluster_balls(
            model, key, max_size=max_size, min_score=min_score
        ):
            i = 0
            merged = False
            to_remove = set()
            for i in range(len(clusters)):
                cluster = clusters[i]
                if (
                    ball == cluster
                    or len(set.intersection(ball, cluster)) == 0
                ):
                    continue
                if ball.issuperset(cluster):
                    to_remove.add(i)
                    continue
                merged = True
                if ball.issubset(cluster):
                    continue
                merge = set.union(ball, cluster)
                if merge in clusters:
                    continue
                clusters[i] = merge
            if not merged and ball not in clusters:
                clusters.append(ball)
            clusters = [
                el for i, el in enumerate(clusters) if i not in to_remove
            ]
    return clusters


def _map_key_to_vector(chunks, stopwords=None, filter_pos=None):
    key2index = {}
    key2vector = {}
    for index, chunk in enumerate(chunks):
        vectors = []
        key = chunk.text.lower()
        for token in chunk:
            if (
                stopwords
                and token.is_stopword
                or filter_pos
                and token.pos_ not in filter_pos
            ):
                continue
            if not np.any(token.vector) or token.vector.size == 0:
                continue
            vectors.append(token.vector)
        if not vectors:
            continue
        key2index.setdefault(key, index)
        key2vector.setdefault(key, sum(vectors) / len(vectors))
    return key2index, key2vector


def _get_neighs_mean_score(model, neighs):
    scores = []
    for neigh, _ in neighs:
        similar = model.most_similar(neigh, topn=1)
        if not similar:
            continue
        _, score = similar[0]
        scores.append(score)
    return sum(scores) / len(scores)


def _get_intruder(model, cluster):
    intruders = Counter()
    maxlen = len(cluster) - 1
    for c in combinations(cluster, maxlen):
        intruder = model.doesnt_match(c)
        intruders.update([intruder])
        if intruders[intruder] == maxlen:
            return intruder
