import importlib
import json
from itertools import chain, combinations
from mmap import mmap
from pathlib import Path
from typing import Iterable, Union

import numpy as np
import regex as re
from bidict import frozenbidict
from cyac import Trie
from scipy import sparse
from scipy.sparse import load_npz, save_npz
from wasabi import msg

from ..util import json_dump, json_load, pickle_dump, pickle_load
from . import dumptools as dt

PGZ = "pages.gz"
RGZ = "redirects.gz"
DGZ = "disambiguations.gz"
CGZ = "categories.gz"
CLGZ = "category_links.npz"


def load(name: Union[Path, str]):
    if isinstance(name, Path):
        if not name.exists():
            raise IOError
        data_path = name
        meta_path = name / "meta.json"
        meta = json.load(meta_path.open())
    elif isinstance(name, str):
        kls = importlib.import_module(name)
        data_path = kls.data_path
        meta = kls.meta
    else:
        raise IOError
    if not data_path.exists():
        raise IOError
    return WikiGraph.load(data_path, meta)


class WikiGraph:
    def __init__(self):
        self.wiki = None
        self.version = None
        self._pages = None
        self._redirects = None
        self._disambiguations = None
        self._categories = None
        self._category_links = None
        self._wpd = WikiPageDetector()

    @staticmethod
    def build(**kwargs):
        wg = WikiGraph()
        wg.wiki = kwargs["wiki"]
        kwargs["version"] = dt.resolve_version(wg.wiki, kwargs["version"])
        wg.version = kwargs["version"]
        p, r, d, c, cl = _make_graph_components(**kwargs)
        wg._pages = frozenbidict(p)
        wg._redirects = r
        wg._disambiguations = frozenbidict(d)
        wg._categories = frozenbidict(c)
        wg._category_links = cl
        pages = wg.pages(redirect=True, disambi=True)
        wg._wpd.build(pages)
        return wg

    @staticmethod
    def load(data_path, meta):
        wg = WikiGraph()
        wg.wiki = meta["wiki"]
        wg.version = meta["version"]
        wg._pages = pickle_load(data_path / PGZ)
        wg._redirects = json_load(data_path / RGZ)
        wg._disambiguations = pickle_load(data_path / DGZ)
        wg._categories = pickle_load(data_path / CGZ)
        wg._category_links = load_npz(str(data_path / CLGZ))
        wg._wpd = WikiPageDetector.load(data_path)
        return wg

    def dump(self, dir_path: Path):
        for value, name in (
            (self._pages, PGZ),
            (self._disambiguations, DGZ),
            (self._categories, CGZ),
        ):
            pickle_dump(
                value,
                dir_path / name,
                compress=True,
            )
        json_dump(self._redirects, dir_path / RGZ, compress=True)
        save_npz(str(dir_path / CLGZ), self._category_links)
        self._wpd.dump(dir_path)

    def is_redirect(self, page: str):
        return page in self._redirects

    def is_disambiguation(self, page: str):
        return page in self._disambiguations

    def is_category(self, page: str):
        return page in self._categories

    def pages(self, redirect: bool = False, disambi: bool = False):
        sources = [self._pages.keys()]
        if redirect:
            sources.append(self._redirects.keys())
        if disambi:
            sources.append(self._disambiguations.keys())
        return (el for el in chain.from_iterable(sources))

    def categories(self):
        return self._categories.keys()

    def redirect(self, page: str):
        if page not in self._redirects:
            return page
        pageid = self._redirects[page]
        if pageid in self._pages.inv:
            return self._pages.inv[pageid]
        if pageid in self._categories.inv:
            return self._categories.inv[pageid]
        if pageid in self._disambiguations.inv:
            return self._disambiguations.inv[pageid]

    def find_pages(self, text: str):
        yield from self._wpd.find_pages(text)

    def get_pageid(self, page: str):
        if page in self._pages:
            return self._pages[page]
        if page in self._redirects:
            return self._redirects[page]
        if page in self._categories:
            return self._categories[page]
        if page in self._disambiguations:
            return self._disambiguations[page]

    def get_categories(self, page: str, distance: int = 1):
        def _recursion_task(pageid, left):
            left -= 1
            for neigh in _get_neighbors(self._category_links, pageid):
                yield self._categories.inv[neigh]
                if not left:
                    continue
                yield from _recursion_task(neigh, left)

        return list(
            set(
                _recursion_task(self.get_pageid(self.redirect(page)), distance)
            )
        )


def _get_neighbors(adjacency, node):
    return adjacency.indices[
        adjacency.indptr[node] : adjacency.indptr[node + 1]
    ]


_XP_SEPS = re.compile(r"(\p{P})")


class WikiPageDetector:
    def __init__(self, pages: Iterable[str] = None):
        self._map = None
        self._trie = None
        if pages is not None:
            self.build(pages)

    @staticmethod
    def load(path: Path):
        wpd = WikiPageDetector()
        wpd._map = pickle_load(path / "wpd_map.gz")
        with (path / "wpd_trie").open("r+b") as bf:
            wpd._trie = Trie.from_buff(mmap(bf.fileno(), 0), copy=False)
        return wpd

    def dump(self, path: Path):
        self._trie.save(str(path / "wpd_trie"))
        pickle_dump(self._map, path / "wpd_map.gz", compress=True)

    def build(self, pages: Iterable[str]):
        key2titles = {}
        for page in pages:
            if not page:
                continue
            key = _clean_title(page).lower()
            if not key:
                key = page
            titles = key2titles.setdefault(key, [])
            titles.append(page)
        mapping = {}
        self._trie = Trie(ignore_case=True)
        for key in key2titles:
            id_ = self._trie.insert(key)
            mapping.setdefault(id_, tuple(key2titles[key]))
        self._map = tuple([mapping.get(i) for i in range(max(mapping) + 1)])

    def find_pages(self, text: str):
        def iter_matches(source):
            ac_seps = set([ord(p) for p in _XP_SEPS.findall(source)])
            for id_, start_idx, end_idx in self._trie.match_longest(
                source, ac_seps
            ):
                yield (start_idx, end_idx, self._map[id_])

        for match in iter_matches(text):
            yield match
            match_text = text[match[0] : match[1]]
            seps = list(_XP_SEPS.finditer(match_text))
            if len(seps) < 1:
                continue
            tokens = []
            last_end = 0
            for sep in seps:
                token = match_text[last_end : sep.start()]
                start = last_end
                last_end = sep.end()
                if len(token) < 2 and not token.isalnum():
                    continue
                tokens.append((start, token))
            tokens.append((last_end, match_text[last_end:]))
            num_tokens = len(tokens)
            for s, e in combinations(range(num_tokens + 1), 2):
                if s == 0 and e == num_tokens:
                    continue
                e -= 1
                submatches = set()
                start = tokens[s][0]
                end = tokens[e][0] + len(tokens[e][1])
                subtext = match_text[start:end]
                start += match[0]
                for sidx, eidx, pages in iter_matches(subtext):
                    coords = (sidx + start, eidx + start)
                    if coords in submatches:
                        continue
                    submatches.add(coords)
                    yield (*coords, pages)


def _make_graph_components(**kwargs):
    cat2id = {}
    page2id = {}
    id2page = {}
    disambiguations = {}
    pprops = _get_pprops(**kwargs)
    verbose = "verbose" in kwargs and kwargs["verbose"]
    msg_no_print = msg.no_print
    msg.no_print = not verbose
    iter_page_data = dt.iter_page_dump_data(**kwargs)
    for ns_kind, pageid, title in iter_page_data:
        disambi = False
        if pageid in pprops:
            page_props = pprops[pageid]
            if "hiddencat" in page_props or "noindex" in page_props:
                continue
            if "disambiguation" in page_props:
                disambi = True
        if disambi:
            disambiguations.setdefault(title, pageid)
        if ns_kind == dt.WIKI_NS_KIND_PAGE:
            page2id[title] = pageid
            id2page[pageid] = title
        elif ns_kind == dt.WIKI_NS_KIND_CATEGORY:
            cat2id[f"Category:{title}"] = pageid
    category_links = _get_category_links(cat2id, id2page, **kwargs)
    redirects = _get_redirects(page2id, id2page, **kwargs)
    with msg.loading("Removing duplicates..."):
        for title in redirects.values():
            source_id = page2id.pop(title, None)
            id2page.pop(source_id, None)
        for title, pageid in disambiguations.items():
            page2id.pop(title, None)
            id2page.pop(pageid, None)
    with msg.loading("Building graph..."):
        adjacency = _edgelist2adjacency(category_links)
    msg.no_print = msg_no_print
    return page2id, redirects, disambiguations, cat2id, adjacency


def _get_pprops(**kwargs):
    pprops = {}
    iter_pprops_data = dt.iter_page_props_dump_data(**kwargs)
    for pageid, prop, value in iter_pprops_data:
        page_props = pprops.setdefault(pageid, {})
        page_props.setdefault(prop, value)
    return pprops


def _get_redirects(page2id, id2page, **kwargs):
    redirects = {}
    for source_id, target_title in dt.iter_redirect_dump_data(**kwargs):
        try:
            page = id2page[source_id]
            target_id = page2id[target_title]
        except KeyError:
            continue
        redirects.setdefault(page, target_id)
    # fix re-redirects
    for page, target_id in redirects.items():
        target = id2page[target_id]
        if target not in redirects:
            continue
        re_target_id = redirects[target]
        if re_target_id == target_id:
            continue
        redirects[page] = re_target_id
    return redirects


def _get_category_links(cat2id, id2page, **kwargs):
    trie = Trie()
    for page in id2page.values():
        trie.insert(page)
    category_links = []
    for cl_type, source_id, target_title in dt.iter_categorylinks_dump_data(
        **kwargs
    ):
        if (
            # only categories with a page
            target_title not in trie
            # only allowed pages
            or cl_type == dt.WIKI_CL_TYPE_PAGE
            and source_id not in id2page
        ):
            continue
        try:
            target_id = cat2id[f"Category:{target_title}"]
        except KeyError:
            continue
        category_links.append((source_id, target_id))
    return category_links


def _clean_title(title: str):
    open_at = title.find("_(")
    if open_at < 0:
        return title
    close_at = title.find(")", open_at)
    if close_at < 0:
        return title
    a = title[:open_at]
    b = title[close_at + 1 :]
    return "".join((a, b))


def _edgelist2adjacency(edgelist: list) -> sparse.csr_matrix:
    """
    Code adapted from **scikit-network**:
    https://github.com/sknetwork-team/scikit-network/blob/master/sknetwork/utils/parse.py

    Build an adjacency matrix from a list of edges.

    Parameters
    ----------
    edgelist : list
        List of edges as pairs (i, j) or triplets (i, j, w) for weighted edges.
    undirected : bool
        If ``True``, return a symmetric adjacency.

    Returns
    -------
    adjacency : sparse.csr_matrix

    Examples
    --------
    >>> edgelist = [(0, 1), (1, 2), (2, 0)]
    >>> adjacency = edgelist2adjacency(edgelist)
    >>> adjacency.shape, adjacency.nnz
    ((3, 3), 3)
    >>> adjacency = edgelist2adjacency(edgelist, undirected=True)
    >>> adjacency.shape, adjacency.nnz
    ((3, 3), 6)
    >>> weighted_edgelist = [(0, 1, 0.2), (1, 2, 4), (2, 0, 1.3)]
    >>> adjacency = edgelist2adjacency(weighted_edgelist)
    >>> adjacency.dtype
    dtype('float64')
    """
    edges = np.array(edgelist)
    row, col = edges[:, 0].astype(np.int32), edges[:, 1].astype(np.int32)
    n = max(row.max(), col.max()) + 1
    if edges.shape[1] > 2:
        data = edges[:, 2]
    else:
        data = np.ones_like(row, dtype=bool)
    adjacency = sparse.csr_matrix((data, (row, col)), shape=(n, n))
    return adjacency
