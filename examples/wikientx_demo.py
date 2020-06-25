import spacy
import streamlit as st
from ftfy import fix_text
from spacy import displacy

from respacy.entity_linking.wikientx import WikiEntX


@st.cache(allow_output_mutation=True, show_spinner=False)
def nlp():
    return spacy.load("en_core_web_sm")


@st.cache(
    hash_funcs={WikiEntX: id}, allow_output_mutation=True, show_spinner=False,
)
def wikientx():
    return WikiEntX()


@st.cache(show_spinner=False)
def get_entities_and_clusters(text):
    clusters = {}
    wiki_ents = {}
    wiki_spans = []
    _nlp = nlp()
    _wikientx = wikientx()
    doc = _wikientx(_nlp(text))
    for chunk in doc._.wiki_chunks:
        wiki_span = {"start": chunk.start_char, "end": chunk.end_char}
        chunk_ents = []
        for (page, ents, score) in chunk._.wiki_ents:
            ent_titles = []
            name = page["name"]
            title = page["title"]
            wiki_span["label"] = title
            for ent in ents:
                ent_title = ent["title"]
                ent_titles.append(ent_title)
                if ent_title not in clusters:
                    clusters[ent_title] = 0
                clusters[ent_title] += 1
            chunk_ents.append((name, title, ent_titles))
        wiki_spans.append(wiki_span)
        if chunk.text in wiki_ents:
            continue
        wiki_ents[chunk.text] = chunk_ents
    wiki_spans.sort(key=lambda x: x["start"])
    return wiki_spans, wiki_ents, clusters


def main():
    st.title("WikiEntX DEMO")
    nlp()
    wikientx()
    uploaded_file = st.file_uploader("Select a text file", type="txt")
    if uploaded_file is None:
        return

    with st.spinner("Loading..."):
        text = fix_text(uploaded_file.read())
        wiki_spans, wiki_ents, clusters = get_entities_and_clusters(text)

    st.header("Clustering")
    st.json(
        {
            k: v
            for k, v in sorted(
                clusters.items(), key=lambda x: x[1], reverse=True
            )
        }
    )

    st.header("Entities")
    st.json(wiki_ents)

    st.header("Document")
    renderer = displacy.EntityRenderer()
    st.write(
        renderer.render_ents(text, wiki_spans, None), unsafe_allow_html=True
    )


if __name__ == "__main__":
    main()
