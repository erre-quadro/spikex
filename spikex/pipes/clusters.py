from collections import Counter
from itertools import combinations
from random import randrange
from typing import List

import numpy as np
from gensim.models import KeyedVectors
from spacy.tokens import Doc, Span

from spikex.defaults import spacy_version

if spacy_version >= 3:
    from spacy.language import Language

    @Language.factory("clusterx")
    def create_clusterx(nlp, name):
        return ClusterX()


class ClusterX:
    """
    Cluster `noun_chunks` of a `Doc` by applying a revisited **Radial Ball Mapper** algorithm.
    """

    def __init__(self, min_score: float):
        Doc.set_extension("cluster_chunks", default=[], force=True)
        self.min_score = min_score

    def __call__(self, doc: Doc):
        doc._.cluster_chunks = cluster_chunks(
            list(doc.noun_chunks), min_score=self.min_score
        )
        return doc


def cluster_chunks(
    chunks: List[Span],
    stopwords: bool = False,
    filter_pos: List[str] = None,
    min_score: float = None,
):
    """
    Cluster chunks by using a revisited **Radial Ball Mapper** algorithm

    Parameters
    ----------
    chunks : List[Span]
        Chunks to cluster.
    stopwords : bool, optional
        Flag to exclude stopwords from chunks, by default False.
    filter_pos : List[str], optional
        POS tags to filter chunk words, by default None
    min_score : float, optional
        Threshold for clustering chunks, by default None

    Returns
    -------
    List[List[Span]]
        Clusters of chunks
    """
    key2index, key2vector = _map_key_to_vector(chunks, stopwords, filter_pos)
    if not key2index or not key2vector:
        return
    model = KeyedVectors(chunks[0].vector.size)
    keys = list(key2vector.keys())
    weights = list(key2vector.values())
    model.add_vectors(keys, weights)
    clusters = cluster_balls_multi(model, keys, min_score=min_score)
    return [[chunks[key2index[i]] for i in cluster] for cluster in clusters]


def cluster_balls(
    model: KeyedVectors,
    root: str = None,
    max_size: int = None,
    min_score: float = None,
):
    """
    Cluster a model's keys by applying a revisited Radial Ball Mapper algorithm.

    A root key should be specified in case a point of interest is known.
    Not specifying any root key, a random one is picked from the model.

    If no otherwise specified, a `max_size` of 30 is used by default.

    if no otherwise specified, a `min_score` calculated as mean of all best similarities,
    minus a gap of 0.05, is used by default.

    Parameters
    ----------
    model : KeyedVectors
        Word2Vec model which stores all keys and vectors.
    root : str
        Point of interest from which to start clustering balls, by default None.
    max_size : int, optional
        Maximum size of a ball in terms of number of keys, by default None.
    min_score : float, optional
        Minimum similarity threshold for starting a cluster, by default None.

    Returns
    -------
    List[List[str]]
        Clusters of keys
    """
    if root is None:
        rand_i = randrange(0, len(model.index_to_key))
        root = model.index_to_key[rand_i]
    elif root not in model:
        return
    max_size = max_size or 30
    neighs = model.most_similar(root, topn=max_size)
    if not neighs:
        return
    if min_score is None:
        mean = _get_neighs_mean_score(model, neighs)
        min_score = min(neighs[0][1], mean - 0.10)
    clusters = []
    root_cluster = {root}
    seen = {root: (root_cluster, 1)}
    for n, s in neighs:
        if n in seen:
            continue
        if s >= min_score:
            root_cluster.add(n)
            seen.setdefault(n, (root_cluster, s))
            continue
        cluster = set()
        min_sub_score = min_score + 0.10
        for nn, ss in model.most_similar(n, topn=max_size):
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


def cluster_balls_multi(
    model: KeyedVectors,
    keys: List[str],
    max_size: int = None,
    min_score: float = None,
):
    """
    Cluster a model's keys by applying a revisited Radial Ball Mapper algorithm
    to each key of a list, fixing overlappings in order to build coherent clusters.

    This provides a method to create clusters based on multiple points of interest instead of one only.

    Parameters
    ----------
    model : KeyedVectors
        Word2Vec model which stores all keys and vectors.
    keys : List[str]
        Keys to use as points of interest.
    max_size : int, optional
        Maximum size of a ball in terms of number of keys, by default None.
    min_score : float, optional
        Minimum similarity threshold for starting a cluster, by default None.

    Returns
    -------
    List[List[str]]
        Clusters of keys
    """
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
    for neigh, score in neighs:
        if not scores:
            scores.append(score)
        similar = model.most_similar(neigh, topn=1)
        if not similar:
            continue
        scores.extend([s[1] for s in similar])
    return sum(scores) / len(scores)


def _get_intruder(model, cluster):
    intruders = Counter()
    maxlen = len(cluster) - 1
    for c in combinations(cluster, maxlen):
        intruder = model.doesnt_match(c)
        intruders.update([intruder])
        if intruders[intruder] == maxlen:
            return intruder
