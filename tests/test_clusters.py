from spikex.clusters import cluster_chunks


def test_clusters(nlp):
    chunks = [
        nlp(chunk)
        for chunk in (
            "yellow",
            "red",
            "orange",
            "violet",
            "purple",
            "black",
            "white",
        )
    ]
    clusters = cluster_chunks(chunks)
    assert len(clusters) == 2
    assert set(clusters[0]) == set(chunks[:5])
    assert set(clusters[1]) == set(chunks[5:])
