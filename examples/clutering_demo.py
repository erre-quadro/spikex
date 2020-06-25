from collections import Counter
import spacy
import streamlit as st
from ftfy import fix_text
from spacy import displacy
from pathlib import Path
from srsly import json_loads

from respacy.clustering.wikicluster import WikiCluster


MAX_DOCS = 10


@st.cache(allow_output_mutation=True, show_spinner=False)
def nlp():
    return spacy.load("en_core_web_sm")


@st.cache(
    hash_funcs={WikiCluster: id}, allow_output_mutation=True, show_spinner=False,
)
def wikicluster():
    return WikiCluster()


@st.cache(allow_output_mutation=True, show_spinner=False)
def load_patents():
    _nlp = nlp()
    return [
        {
            _nlp("\n".join([el for lines in patent.values() for el in lines])): patent["uid"]
            for patent in json_loads(path.read_text())[:MAX_DOCS]
        }
        for path in Path("resources/patents").glob("**/*.json")
    ]


@st.cache(allow_output_mutation=True, show_spinner=False)
def _get_linkage():
    docs_groups = load_patents()
    docs = {d: uid for group in docs_groups for d, uid in group.items()}
    _wcl = wikicluster()
    return _wcl(docs)


@st.cache(allow_output_mutation=True, show_spinner=False)
def get_clusters():
    docs_groups = load_patents()
    docs = {d: uid for group in docs_groups for d, uid in group.items()}
    groups = {uid: i for i, group in enumerate(docs_groups) for uid in group.values()}
    seen = set()
    clusters = []
    linkage = _get_linkage()
    th = 0.34
    print("\n".join([f"{docs[d1]}/{groups[docs[d1]]} -> {docs[d2]}/{groups[docs[d2]]} : {c}" for d1, mts in linkage.items() for d2, c in mts.items()]))
    for el1, mts in linkage.items():
        cluster = set([el1])
        adding = set([el for el in mts if mts[el] >= th])
        while adding and len(adding) > 0:
            el2 = adding.pop()
            if el2 in seen:
                continue
            seen.add(el2)
            cluster.add(el2)
            if el2 not in linkage:
                continue
            for new_el, correl in linkage[el2].items():
                if correl < th:
                    continue
                adding.add(new_el)
        clusters.append(cluster)
    for d in set.difference(set(docs), seen):
        clusters.append([d])
    clusters = [
        [f"{docs[el]}/{groups[docs[el]]}" for el in cluster]
        for cluster in clusters
    ]
    stats = {}
    for cluster in clusters:
        count = Counter()
        for uid in cluster:
            cut_at = uid.find("/")
            uid = uid[:cut_at]
            count.update([groups[uid]])
        for i, c in count.most_common():
            if i not in stats or stats[i] < c:
                stats[i] = c
    stats = [[(i, (c * 100) / MAX_DOCS)] for i, c in stats.items()]
    return clusters, stats


def main():
    st.title("WikiCluster DEMO")
    nlp()
    wikicluster()
    with st.spinner("Loading..."):
        clusters, stats = get_clusters()
    st.table(stats)
    st.table(clusters)


if __name__ == "__main__":
    main()
