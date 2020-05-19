import spacy
import streamlit as st
from ftfy import fix_text

from respacy.entity_linking.wikientx import WikiEntX

HTML_WRAPPER = """
<div style="overflow-x: auto; border: 1px solid #e6e9ef; border-radius: 0.25rem; padding: 1rem; margin-bottom: 2.5rem">{}</div>
"""


@st.cache(allow_output_mutation=True, show_spinner=False)
def nlp():
    return spacy.load("en_core_web_sm")


@st.cache(allow_output_mutation=True, show_spinner=False)
def wikientx():
    return WikiEntX()


def main():
    st.title("WikiEntX DEMO")
    _nlp = nlp()
    _wikientx = wikientx()
    uploaded_file = st.file_uploader("Select a text file", type="txt")
    if uploaded_file is None:
        return

    with st.spinner("Loading..."):
        text = fix_text(uploaded_file.read())
        doc = _wikientx(_nlp(text))

    st.write(HTML_WRAPPER.format(text), unsafe_allow_html=True)

    st.header("Clustering")
    wiki_chunks_ctx = {}
    for ctx, chunks in sorted(
        doc._.wiki_chunks_ctx.items(), key=lambda x: len(x[1]), reverse=True
    ):
        wiki_chunks_ctx[f"{ctx} - {len(chunks)}"] = [
            t.text for c in chunks for t in c
        ]
    st.json(wiki_chunks_ctx)

    st.header("Entities")
    wiki_ents = {}
    for chunk in doc._.wiki_chunks:
        if chunk.text in wiki_ents:
            continue
        wiki_ents[chunk.text] = chunk._.wiki_ents
    st.json(wiki_ents)

    st.header("Clustering by sentence")
    doc2 = _nlp(text)
    for sent in doc2.sents:
        doc_sent = _wikientx(sent.as_doc())
        wiki_chunks_ctx = {}
        for ctx, chunks in sorted(
            doc_sent._.wiki_chunks_ctx.items(),
            key=lambda x: len(x[1]),
            reverse=True,
        ):
            wiki_chunks_ctx[f"{ctx} - {len(chunks)}"] = [
                t.text for c in chunks for t in c
            ]
        st.json(wiki_chunks_ctx)


if __name__ == "__main__":
    main()
