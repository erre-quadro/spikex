from cyac import Trie
from spacy.tokens import Doc

from ..ontographs import WikiGraph
from itertools import combinations
from ..util import span_idx2i


class WikiEntX:
    def __init__(self):
        Doc.set_extension("wiki_ents", default=[], force=True)
        self._ents_map = {}
        self._wikigraph = WikiGraph(version="latest_main_topics")
        self._trie = Trie(ignore_case=True)
        for ent in self._wikigraph.vertices:
            id_ = self._trie.insert(ent)
            self._ents_map[id_] = ent

    def __call__(self, doc: Doc):
        sep = "_"
        text = doc.text.replace(" ", sep)
        ac_sep = set([ord(sep)])
        matches = {}
        for id_, start, end in self._trie.match_longest(text, ac_sep):
            vertex = self._ents_map[id_]
            if vertex not in matches:
                matches[vertex] = []
            span = span_idx2i(doc, start, end)
            matches[vertex].append(span)
        lca = {}
        for vx1, vx2 in combinations(matches.keys(), 2):
            vertices = (vx1, vx2)
            lca_ = self._wikigraph.get_lca(vertices, max_depth=1)
            if len(lca_) == 0:
                continue
            for p in lca_:
                if p not in lca:
                    lca[p] = []
                lca[p].append(vertices)
        for k, v in sorted(lca.items(), key=lambda x: len(x[1]), reverse=True):
            print(k, len(v))
            if len(v) < 30:
                for vv in v:
                    print("\t", vv)
        return doc
