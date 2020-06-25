import json
from collections import Counter

from tqdm import tqdm

from respacy import data

from .. import data
from . import dumptools

__all__ = "WikiGraph"


class WikiGraph:
    def __init__(self, lang="en", version="latest", roots=None):
        self.lang = lang
        self.version = version
        self.roots = roots
        self._edges = {}
        self._redirects = {}
        self._vertex2page = {}
        self._vertex2category = {}
        self.__page2vertex = {}
        self.__category2vertex = {}
        self._setup_graph()
        # self._filter_by(roots)
        # self._filter_by([7345184])
        # self._filter_by([692903, 871525])
        # self._get_main_topics()

    @property
    def leaves(self):
        return self._vertex2page.keys()

    def get_parents(self, vertex: int):
        if vertex in self._redirects:
            vertex = self._redirects[vertex]
        if vertex not in self._edges:
            return []
        return [int(p) for p in self._edges[vertex].keys()]

    def get_children(self, vertex: int):
        if vertex not in self._edges_reverse:
            return []
        return [int(c) for c in self._edges_reverse[vertex]]

    def get_title(self, vertex: int):
        if vertex in self._vertex2category:
            return self._vertex2category[vertex]
        if vertex in self._vertex2page:
            return self._vertex2page[vertex]

    def get_lca(self, vertices, max_depth=2):
        cp_map = {}
        depth = max_depth
        check_vx = {vx: {vx} for vx in vertices}
        while depth >= 0:
            for vx in vertices:
                if vx not in cp_map:
                    cp_map[vx] = set()
                next_check = set()
                for v in check_vx[vx]:
                    p = self.get_parents(v)
                    if not p:
                        continue
                    cp_map[vx].update(p)
                    next_check.update(p)
                check_vx[vx] = next_check
            depth -= 1
        return set.intersection(*[p for p in cp_map.values()])

    def get_path(self, start, end):
        seen = set()
        next_ps = set([end])
        walks = {end: [end]}
        while next_ps is not None and len(next_ps) > 0:
            this_p = next_ps.pop()
            if this_p in seen:
                continue
            seen.add(this_p)
            this_p_cn = self.get_children(this_p)
            if not this_p_cn:
                del walks[this_p]
                continue
            if start in this_p_cn:
                return walks[this_p]
            for vxc in this_p_cn:
                walks[vxc] = [*walks[this_p]]
                walks[vxc].append(vxc)
            del walks[this_p]
            next_ps.update(set(this_p_cn))
        return []

    def are_redirects(self, v1, v2):
        return (
            v1 in self._redirects
            and self._redirects[v1] == v2
            or v2 in self._redirects
            and self._redirects[v2] == v1
            or v1 in self._redirects
            and v2 in self._redirects
            and self._redirects[v1] == self._redirects[v2]
        )

    @property
    def _page2vertex(self):
        if not self.__page2vertex:
            self.__page2vertex.update(
                {v: k for k, v in self._vertex2page.items()}
            )
        return self.__page2vertex

    @property
    def _category2vertex(self):
        if not self.__category2vertex:
            self.__category2vertex.update(
                {v: k for k, v in self._vertex2category.items()}
            )
        return self.__category2vertex

    @property
    def _dumpname(self):
        return f"{self.lang}wiki_{self.version}"

    def _dump(self):
        for obj, fn in (
            (self._edges, "edges"),
            (self._redirects, "redirects"),
            (self._vertex2page, "vertex2page"),
            (self._edges_reverse, "edges_reverse"),
            (self._vertex2category, "vertex2category"),
        ):
            with data.open(f"{fn}.json", "w+", self._dumpname) as fd:
                json.dump(obj, fd, ensure_ascii=False, indent=0)

    def _setup_graph(self):
        self._vertex2page = _load_from_disk(
            "vertex2page",
            folder=self._dumpname,
            fail_callback=lambda: dumptools.get_pageid_title_map(
                self.lang, self.version
            ),
        )
        self._vertex2category = _load_from_disk(
            "vertex2category",
            folder=self._dumpname,
            fail_callback=lambda: dumptools.get_categoryid_title_map(
                self.lang, self.version
            ),
        )
        self._redirects = _load_from_disk(
            "redirects",
            folder=self._dumpname,
            parse_int=True,
            fail_callback=lambda: {
                k: self._page2vertex[v]
                for k, v in dumptools.get_redirectid_target_map(
                    self.lang, self.version
                ).items()
                if v in self._page2vertex
            },
        )
        self._edges = _load_from_disk(
            "edges",
            folder=self._dumpname,
            parse_int=True,
            fail_callback=lambda: {
                sourceid: {
                    self._category2vertex[c]: None
                    for c in (
                        categories
                        if isinstance(categories, list)
                        else [categories]
                    )
                    if c in self._category2vertex
                }
                for sourceid, categories in dumptools.get_categories_linking_map(
                    self.lang, self.version
                ).items()
            },
        )

        self._edges_reverse = _load_from_disk(
            "edges_reverse", folder=self._dumpname, parse_int=True,
        )

    def _fix_edges_hierarchy(self):
        def have_kindred(root, parent, children):
            seen = set()
            next_ps = set([parent])
            while next_ps is not None and len(next_ps) > 0:
                this_p = next_ps.pop()
                if this_p in seen:
                    continue
                seen.add(this_p)
                this_p_cn = self.get_children(parent)
                if not this_p_cn:
                    continue
                if root in this_p_cn:
                    continue
                intersect = set.intersection(set(this_p_cn), set(children))
                if len(intersect) > 0:
                    return True
                next_ps.update(set(this_p_cn))

        edges = {}
        for child, parents in tqdm(self._edges.items()):
            parents = set(parents.keys())
            new_parents = {*parents}
            for p in parents:
                cn = new_parents.difference(set([p]))
                if not have_kindred(child, p, cn):
                    continue
                new_parents.remove(p)
            new_ps = {new_p: None for new_p in new_parents}
            edges.setdefault(child, new_ps)
        self._edges = edges

        # for child, parents in {**self._edges}.items():
        #     if self.get_children(child):
        #         continue
        #     for parent in {*parents.keys()}:
        #         if len(self.get_children(parent)) < 10000:
        #             continue
        #         del self._edges[child][parent]
        #         print(self.get_title(parent), "FROM", self.get_title(child))

        with data.open(f"edges_fix.json", "w+", self._dumpname) as fd:
            json.dump(self._edges, fd, ensure_ascii=False, indent=0)

    def _get_first_super_parents(self, start, ends):
        seen = set()
        ends = set(ends)
        next_cn = set([start])
        while next_cn is not None and len(next_cn) > 0:
            this_c = next_cn.pop()
            if this_c in seen:
                continue
            seen.add(this_c)
            this_c_ps = self.get_parents(this_c)
            if not this_c_ps:
                continue
            intersect = ends.intersection(set(this_c_ps))
            if len(intersect) > 0:
                return intersect
            next_cn.update(set(this_c_ps))
        return []

    def _hidden_categories(self):
        return set(self.get_children(15961454))

    def _filter_by(self, vertices):
        v2c = {}
        edges = {}
        edges_reverse = {}
        seen = set()
        next_subs = set(vertices)
        # Avoid to include `Hidden categories`
        # and any higher category than vertices
        bad_boys = set([15961454])
        bad_boys = set(
            [pvx for pvx in self.get_children(7345184) if pvx not in vertices]
        )
        hidden_cats = self._hidden_categories()
        while next_subs is not None and len(next_subs) > 0:
            vx = next_subs.pop()
            if vx in seen:
                continue
            seen.add(vx)
            # if vx in bad_boys:
            #     continue
            # vx_ps = set(self.get_parents(vx))
            # if len(bad_boys.intersection(vx_ps)) > 0:
            #     bad_boys.add(vx)
            #     continue
            vxt = self.get_title(vx)
            if not vxt:
                continue
            children = self.get_children(vx)
            if not children:
                continue
            v2c.setdefault(vx, vxt)
            reverse = edges_reverse.setdefault(vx, {})
            for vxc in children:
                if any(
                    vxc_p in hidden_cats for vxc_p in self.get_parents(vxc)
                ):
                    continue
                # if vxc in bad_wiki_cats:
                #     continue
                reverse.setdefault(vxc)
                ps = edges.setdefault(vxc, {})
                ps.setdefault(vx)
                next_subs.add(vxc)
        if not edges:
            print("Empty")
            return
        self._edges = {k: v for k, v in edges.items() if v}
        self._edges_reverse = {k: v for k, v in edges_reverse.items() if v}
        self._vertex2category = v2c
        self.__page2vertex = {}
        self.__category2vertex = {}
        self._dump()

    def _get_main_topics(self):
        super_parent = 7345184
        main_topics = self.get_children(super_parent)
        for topic in main_topics:
            for subtopic in self.get_children(topic):
                if subtopic not in self._vertex2category:
                    continue
                count = 0
                counter = Counter()
                for parent in self.get_parents(subtopic):
                    if parent not in self._vertex2category:
                        continue
                    topics = self._get_first_super_parents(parent, main_topics)
                    if not topics:
                        continue
                    count += len(topics)
                    counter.update(topics)
                percent = [
                    (self.get_title(t), c * 100 / count)
                    for t, c in counter.most_common()
                ]
                print(self.get_title(topic), self.get_title(subtopic), percent)


def _load_from_disk(filename, folder=None, parse_int=None, fail_callback=None):
    fn = filename if filename.endswith(".json") else (filename + ".json")
    if not data.contains(fn, folder):
        if not fail_callback:
            return
        obj = fail_callback()
        with data.open(f"{fn}", "w+", folder) as fd:
            json.dump(obj, fd, ensure_ascii=False, indent=0)
        return obj
    with data.open(f"{fn}", "r", folder) as fd:
        keys_as_int_hook = lambda x: {
            int(k): int(v) if isinstance(v, str) and parse_int else v
            for k, v in x
        }
        return json.load(fd, object_pairs_hook=keys_as_int_hook)
