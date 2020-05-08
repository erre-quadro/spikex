import json
from concurrent.futures import ProcessPoolExecutor, as_completed
from functools import partial
from pathlib import Path
from typing import List, Union

from ftfy import fix_text
from smart_open.compression import compression_wrapper
from smart_open.http import open as http_open
from tqdm import tqdm

from respacy import data

from .. import data

__all__ = "WikiGraph"


class WikiGraph:
    def __init__(self, lang="en", version="latest"):
        self._lang = lang
        self._version = version
        self._edges = {}
        self._redirects = {}
        self._vertex2title = {}
        self._edges_reverse = {}
        self.__title2vertex = {}
        if not self._load_from_disk():
            self._setup_graph()
            self._dump()
        # self._clean()

    @property
    def vertices(self):
        return self._vertex2title.values()

    def get_parents(self, vertex: Union[str, int]):
        vx = self._get_vertex(vertex)
        if not vx:
            return
        return [self._vertex2title[v] for v in self._edges[vx]]

    def get_children(self, vertex: Union[str, int]):
        vx = self._get_vertex(vertex)
        if not vx or vx not in self._edges_reverse:
            return
        return [
            self._vertex2title[v] 
            for v in self._edges_reverse[vx] 
            if v in self._vertex2title
        ]

    def get_subgraph(self, vertices: List[Union[str, int]]):
        def rec_subgraph(vxs, edges):
            _edges = {c: vx for vx in vxs for c in self.get_children(vx)}
            if not _edges:
                return edges
            edges.update(_edges)
            return rec_subgraph(_edges.keys(), edges)

        return rec_subgraph(vertices, {})

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

    @property
    def _title2vertex(self):
        if not self.__title2vertex:
            self.__title2vertex = {
                v: k 
                for k, v in self._vertex2title.items()
            }
        return self.__title2vertex

    @property
    def _dumpname(self):
        return f"{self._lang}wiki_graph_{self._version}"

    def _dump(self):
        for obj, fn in (
            (self._edges, "edges"),
            (self._redirects, "redirects"),
            (self._vertex2title, "vertex2title"),
        ):
            with data.open(f"{fn}.json", "w+", self._dumpname) as fd:
                json.dump(obj, fd, ensure_ascii=False, indent=0)

    def _load_from_disk(self):
        if not data.contains(self._dumpname):
            return False
        for obj, fn in (
            (self._edges, "edges"),
            (self._redirects, "redirects"),
            (self._vertex2title, "vertex2title"),
            (self._edges_reverse, "edges_reverse"),
        ):
            with data.open(f"{fn}.json", "r", self._dumpname) as fd:
                obj.update(json.load(fd))
        return True

    def _setup_graph(self):
        self._vertex2title = _get_pageid_title_map(self._lang, self._version)
        self._redirects = {
            k: self._title2vertex[v]
            for k, v in _get_redirectid_target_map(
                self._lang, self._version
            ).items()
            if v in self._title2vertex
        }
        sourceid2categories = _get_categories_linking_map(
            self._lang, self._version
        )
        for sourceid, categories in sourceid2categories.items():
            if isinstance(categories, str):
                categories = [categories]
            vertices = {
                self._title2vertex[c]: None
                for c in categories
                if c in self._title2vertex
            }
            self._edges.setdefault(sourceid, vertices)

    def _get_vertex(self, vertex: Union[str, int]):
        if isinstance(vertex, str):
            if vertex not in self._title2vertex:
                return
            vertex = self._title2vertex[vertex]
        if vertex in self._redirects:
            vx = self._redirects[vertex]
            if vx not in self._edges:
                return
            return vx
        if vertex in self._edges:
            return vertex

    def _clean(self):
        v2t = {}
        edges = {}
        seen = set()
        next_subs = set(["Main_topic_classifications"])
        while next_subs is not None and len(next_subs) > 0:
            vx = next_subs.pop()
            if vx in seen:
                continue
            seen.add(vx)
            children = self.get_children(vx)
            if not children:
                continue
            v2t.setdefault(self._title2vertex[vx], vx)
            for child in children:
                cvx = self._title2vertex[child]
                v2t.setdefault(cvx, child)
                ps = edges.setdefault(cvx, {})
                ps.setdefault(self._title2vertex[vx])
                next_subs.add(child)
        if not edges:
            return
        self._edges = edges
        self._vertex2title = v2t
        self.__title2vertex = {}
        self._dump()


WIKI_DP_PAGE = "page"
WIKI_DP_REDIRECT = "redirect"
WIKI_DP_CATEGORYLINKS = "categorylinks"
WIKI_DL_NAME = "{l}wiki-{v}-{t}.sql.gz"
WIKI_DL_PATH = "https://dumps.wikimedia.org/{l}wiki/{v}/{n}"
WIKI_NS_PAGE_CATEGORY = ("0", "14")  # 0: Main page, 14: Category


def _get_pageid_title_map(l, v):
    dump_url = _get_wiki_dump_dl_url(l, WIKI_DP_PAGE, v)
    return _parse_wiki_sql_dump(dump_url, _parse_fx_pageid_title_map)


def _parse_fx_pageid_title_map(el):
    if el[1] not in WIKI_NS_PAGE_CATEGORY:
        return
    pageid = el[0]
    title = fix_text(el[2])
    return pageid, title


def _get_redirectid_target_map(l, v):
    dump_url = _get_wiki_dump_dl_url(l, WIKI_DP_REDIRECT, v)
    return _parse_wiki_sql_dump(dump_url, _parse_fx_redirectid_target_map)


def _parse_fx_redirectid_target_map(el):
    if el[1] not in WIKI_NS_PAGE_CATEGORY:
        return
    redirectid = el[0]
    title = fix_text(el[2])
    return redirectid, title


def _get_categories_linking_map(l, v):
    dump_url = _get_wiki_dump_dl_url(l, WIKI_DP_CATEGORYLINKS, v)
    return _parse_wiki_sql_dump(dump_url, _parse_fx_categories_linking_map)


def _parse_fx_categories_linking_map(el):
    if el[6] not in ("page", "subcat"):
        return
    sourceid = el[0]
    target = fix_text(el[1])
    return sourceid, target


def _get_wiki_dump_dl_url(l, t, v):
    n = WIKI_DL_NAME.format(l=l, t=t, v=v)
    return Path(WIKI_DL_PATH.format(l=l, n=n, v=v))


def _parse_wiki_sql_dump(wiki_sql_dump_url, parse_fx):
    with ProcessPoolExecutor(max_workers=4) as executor:
        fs = []
        mode = "rb"
        compress_bytes_read = 0
        if data.contains(wiki_sql_dump_url.name):
            compress_obj = data.open(wiki_sql_dump_url.name, mode=mode)
            content_len = data.force_get(wiki_sql_dump_url.name).stat().st_size
        else:
            compress_obj = http_open(wiki_sql_dump_url, mode=mode)
            content_len = int(
                compress_obj.response.headers.get("content-length")
            )
        with tqdm(
            desc=f"Parsing {wiki_sql_dump_url.name}",
            total=content_len,
            unit="B",
            unit_scale=True,
            unit_divisor=1024,
        ) as pbar, compression_wrapper(compress_obj, mode) as decompress_obj:
            for line in decompress_obj:
                task = partial(_parsing_task, parse_fx=parse_fx)
                fs.append(executor.submit(task, line.decode("latin-1")))
                compress_bytes = compress_obj.tell()
                pbar.update(compress_bytes - compress_bytes_read)
                compress_bytes_read = compress_bytes
            compress_obj.close()
        d = {}
        with tqdm(desc="Collecting", total=len(fs)) as pbar:
            for f in as_completed(fs):
                for res in f.result():
                    if not res:
                        continue
                    k, v = res
                    if k in d:
                        t = d[k]
                        if isinstance(t, set):
                            d[k].add(v)
                        else:
                            d[k] = set((d[k], v))
                    else:
                        d[k] = v
                pbar.update(1)
        return d


def _parsing_task(line, parse_fx):
    return [parse_fx(el) for el in _parse_wiki_sql_dump_line(line)]


def _parse_wiki_sql_dump_line(line):
    if line.startswith("INSERT INTO"):
        el_end = 0
        el_start = 0
        curr_tuple = []
        is_escaping = False
        is_string_open = False
        line_start = line.index("(")
        for i in range(line_start, len(line)):
            c = line[i]
            if not is_string_open:
                if c == "(":
                    el_start = i + 1
                    continue
                if c == ")":
                    el_end = i if el_end == 0 else el_end
                    el = "" if el_start == el_end else line[el_start:el_end]
                    curr_tuple.append(el)
                    el_end = 0
                    el_start = 0
                    if curr_tuple:
                        yield tuple(curr_tuple)
                        curr_tuple = []
                    continue
                if c == ",":
                    if el_start > 0:
                        el_end = i if el_end == 0 else el_end
                        el = (
                            "" if el_start == el_end else line[el_start:el_end]
                        )
                        curr_tuple.append(el)
                        el_end = 0
                        el_start = i + 1
                    continue
                if c == "'":
                    el_start = i + 1
                    is_string_open = True
                    continue
            else:
                if c == "\\":
                    is_escaping = not is_escaping
                elif c == "'" and not is_escaping:
                    el_end = i
                    is_string_open = False
                    continue
                else:
                    is_escaping = False
