from collections import Counter
from pathlib import Path

import spacy
import streamlit as st
from srsly import json_loads

from respacy.clustering.wikiclusterx import WikiClusterX


@st.cache(allow_output_mutation=True, show_spinner=False)
def nlp():
    return spacy.load("en_core_web_sm")


@st.cache(
    hash_funcs={WikiClusterX: id},
    allow_output_mutation=True,
    show_spinner=False,
)
def wikicluster():
    return WikiClusterX(nlp().vocab)


@st.cache(allow_output_mutation=True, show_spinner=False)
def load_patent(path):
    return


@st.cache(allow_output_mutation=True, show_spinner=False)
def load_patents(num_docs):
    _nlp = nlp()
    return [
        {
            _nlp(
                "\n".join(
                    [
                        el
                        for lines in patent.values()
                        for el in lines
                        if isinstance(lines, list)
                    ]
                )
            ): patent["uid"]
            for patent in json_loads(path.read_text())["response"]["docs"][
                :num_docs
            ]
        }
        for path in Path("resources/patents").glob("**/*.json")
    ]


@st.cache(allow_output_mutation=True, show_spinner=False)
def _get_linkage(num_docs):
    docs_groups = load_patents(num_docs)
    docs = {d: uid for group in docs_groups for d, uid in group.items()}
    _wcl = wikicluster()
    return _wcl(docs)


@st.cache(allow_output_mutation=True, show_spinner=False)
def get_clusters(num_docs, th):
    docs_groups = load_patents(num_docs)
    docs = {d: uid for group in docs_groups for d, uid in group.items()}
    groups = {
        uid: i for i, group in enumerate(docs_groups) for uid in group.values()
    }
    seen = set()
    clusters = []
    linkage = _get_linkage(num_docs)
    # print(
    #     "\n".join(
    #         [
    #             f"{docs[d1]}/{groups[docs[d1]]} -> {docs[d2]}/{groups[docs[d2]]} : {c}"
    #             for d1, mts in linkage.items()
    #             for d2, c in mts.items()
    #         ]
    #     )
    # )
    for el1, mts in linkage.items():
        cluster = set([el1])
        adding = set([el for el in mts if mts[el][0] >= th])
        while adding and len(adding) > 0:
            el2 = adding.pop()
            if el2 in seen:
                continue
            seen.add(el2)
            cluster.add(el2)
            if el2 not in linkage:
                continue
            for new_el, correl in linkage[el2].items():
                if correl[0] < th:
                    continue
                adding.add(new_el)
        clusters.append(cluster)
    for d in set.difference(set(docs.values()), seen):
        clusters.append([d])
    # -----------------------------------------
    for i, cluster in enumerate(clusters):
        if len(cluster) < 2:
            continue
        good_ents = {}
        for doc in cluster:
            if doc not in linkage:
                continue
            for el, mts in linkage[doc].items():
                if el not in cluster or el == doc:
                    continue
                for el1 in mts[1]:
                    if el1[0] not in good_ents or good_ents[el1[0]] < el1[1]:
                        good_ents[el1[0]] = el1[1]
        print(
            "CLUSTER:",
            ", ".join(cluster),
            "\n",
            ", ".join(
                [
                    f"{e} ({c})"
                    for e, c in sorted(
                        good_ents.items(), key=lambda x: x[1], reverse=True
                    )
                ]
            ),
        )
    # -----------------------------------------
    clusters = [
        [f"{el}/{groups[el]}" for el in cluster] for cluster in clusters
    ]
    stats = {}
    for cluster in clusters:
        count = Counter()
        clen = len(cluster)
        for uid in cluster:
            cut_at = uid.find("/")
            uid = uid[:cut_at]
            count.update([groups[uid]])
        for i, c in count.most_common():
            if i not in stats or stats[i][0] < c:
                stats[i] = (c, c / clen)
    stats = [
        [(i, f"r: {c[0] / num_docs:.2f}", f"p: {c[1]:.2f}")]
        for i, c in stats.items()
    ]
    return clusters, stats


def main():
    st.title("WikiCluster DEMO")
    nlp()
    wikicluster()
    num_docs = st.slider("Number of docs", 10, 100, 10, 10)
    th = st.slider("Clusterization threshold", 0.0, 1.0, 0.25, 0.05)
    with st.spinner("Loading..."):
        clusters, stats = get_clusters(num_docs, th)
    st.table(stats)
    st.table(clusters)


if __name__ == "__main__":
    main()
