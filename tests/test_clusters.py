from spikex.clusters import cluster_chunks


def test_clusters(nlp):
    chunks = [
        nlp(chunk)
        for chunk in (
            "orange",
            "mango",
            "papaya",
            "indigo",
            "red",
            "violet",
            "purple",
        )
    ]
    clusters = sorted(cluster_chunks(chunks), key=len)
    assert len(clusters) == 3
    assert set(clusters[0]) == set(chunks[:1])
    assert set(clusters[1]) == set(chunks[1:3])
    assert set(clusters[2]) == set(chunks[3:])
