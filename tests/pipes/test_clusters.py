from spikex.pipes.clusters import ClusterX, cluster_chunks


def test_cluster_chunks(nlp):
    chunks = [
        nlp(chunk)
        for chunk in (
            "gray",
            "black",
            "dog",
            "cat",
        )
    ]
    clusters = sorted(cluster_chunks(chunks), key=len)
    assert len(clusters) == 2
    assert set(clusters[0]) == set(chunks[:2])
    assert set(clusters[1]) == set(chunks[2:4])


def test_clusterx(nlp):
    clusterx = ClusterX(min_score=0.6)
    doc = clusterx(
        nlp("Grab this juicy orange and watch a dog chasing a cat.")
    )
    assert len(doc._.cluster_chunks) == 2
