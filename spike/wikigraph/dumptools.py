from concurrent.futures import ProcessPoolExecutor, as_completed
from functools import partial
from pathlib import Path

import regex as re
import requests
from ftfy import fix_text
from smart_open.compression import compression_wrapper
from smart_open.http import open as http_open
from tqdm import tqdm
from wasabi import msg
from yarl import URL

__all__ = [
    "iter_page_dump_data",
    "iter_redirect_dump_data",
    "iter_categorylinks_dump_data",
]

config = {
    "dumps_path": None,
    "max_workers": 4,
    "verbose": None,
    "version": "latest",
    "wiki": "en",
}

WIKI_NS_KIND_CATEGORY = "14"
WIKI_NS_KIND_PAGE = "0"

WIKI_CL_TYPE_CATEGORY = "subcat"
WIKI_CL_TYPE_PAGE = "page"

_WIKI_DP_CATEGORYLINKS = "categorylinks"
_WIKI_DP_PAGE = "page"
_WIKI_DP_PAGE_PROPS = "page_props"
_WIKI_DP_REDIRECT = "redirect"

_WIKI_DL_NAME = "{w}wiki-{v}-{t}.sql.gz"
_WIKI_BASE_DL_PATH = "https://dumps.wikimedia.org/{w}wiki/"
_WIKI_DL_PATH = _WIKI_BASE_DL_PATH + "{v}/{n}"


def resolve_version(wiki, version):
    url = _WIKI_BASE_DL_PATH.format(w=wiki)
    response = requests.get(url)
    versions = re.findall(r"href=\"(\d+)/\"", response.text)
    if version in versions:
        return version
    if version == "latest":
        return max(versions)
    msg.fail(
        "Wikipedia dump version not found",
        f"Pick one of these: {', '.join(versions)}.",
    )
    return


def iter_page_props_dump_data(**kwargs):
    dump_url = _get_wiki_dump_dl_url(_WIKI_DP_PAGE_PROPS, **kwargs)
    return _parse_wiki_sql_dump(dump_url, _parse_fx_page_props_dump, **kwargs)


def _parse_fx_page_props_dump(el):
    pageid = el[0]
    prop = el[1]
    value = el[2]
    return pageid, prop, value


def iter_page_dump_data(**kwargs):
    dump_url = _get_wiki_dump_dl_url(_WIKI_DP_PAGE, **kwargs)
    return _parse_wiki_sql_dump(dump_url, _parse_fx_page_dump, **kwargs)


def _parse_fx_page_dump(el):
    if el[1] not in (WIKI_NS_KIND_CATEGORY, WIKI_NS_KIND_PAGE):
        return
    ns_kind = el[1]
    pageid = el[0]
    title = fix_text(el[2])
    return ns_kind, pageid, title


def iter_redirect_dump_data(**kwargs):
    dump_url = _get_wiki_dump_dl_url(_WIKI_DP_REDIRECT, **kwargs)
    yield from _parse_wiki_sql_dump(
        dump_url, _parse_fx_redirect_dump, **kwargs
    )


def _parse_fx_redirect_dump(el):
    if el[1] not in (WIKI_NS_KIND_CATEGORY, WIKI_NS_KIND_PAGE):
        return
    redirectid = el[0]
    title = fix_text(el[2])
    return redirectid, title


def iter_categorylinks_dump_data(**kwargs):
    dump_url = _get_wiki_dump_dl_url(_WIKI_DP_CATEGORYLINKS, **kwargs)
    return _parse_wiki_sql_dump(
        dump_url, _parse_fx_categorylinks_dump, **kwargs
    )


def _parse_fx_categorylinks_dump(el):
    if el[6] not in (WIKI_CL_TYPE_CATEGORY, WIKI_CL_TYPE_PAGE):
        return
    cl_type = el[6]
    sourceid = el[0]
    target = fix_text(el[1])
    return cl_type, sourceid, target


def _get_wiki_dump_dl_url(t, **kwargs):
    _kwargs = {**config, **kwargs}
    w = _kwargs["wiki"]
    v = _kwargs["version"]
    n = _WIKI_DL_NAME.format(w=w, t=t, v=v)
    dp = _kwargs["dumps_path"]
    if dp is not None and dp.exists():
        path = dp.joinpath(n)
        if path.exists():
            return path
    return URL(_WIKI_DL_PATH.format(w=w, n=n, v=v))


def _parse_wiki_sql_dump(wiki_sql_dump_url, parse_fx, **kwargs):
    _kwargs = {**config, **kwargs}
    dumps_path = _kwargs["dumps_path"]
    max_workers = _kwargs["max_workers"]
    verbose = _kwargs["verbose"]
    fs = []
    compress_bytes_read = 0
    dump_name = wiki_sql_dump_url.name
    msg.text(f"-> {dump_name}", show=verbose)
    compress_obj, content_len = _get_wiki_dump_obj(wiki_sql_dump_url, verbose)
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        tqdm_disable = not verbose
        tqdm_kwargs = {
            "unit": "B",
            "unit_scale": True,
            "unit_divisor": 1024,
            "disable": tqdm_disable,
        }
        with tqdm(
            desc="parse", total=content_len, **tqdm_kwargs,
        ) as pbar, compression_wrapper(compress_obj, "rb") as decompress_obj:
            for line in decompress_obj:
                task = partial(_parsing_task, parse_fx=parse_fx)
                fs.append(executor.submit(task, line.decode("latin-1")))
                compress_bytes = compress_obj.tell()
                pbar.update(compress_bytes - compress_bytes_read)
                compress_bytes_read = compress_bytes
        if dumps_path is not None:
            compress_obj.seek(0)
            if not dumps_path.exists():
                dumps_path.mkdir()
            dump_filepath = dumps_path.joinpath(dump_name)
            if not dump_filepath.exists() or dump_filepath.stat().st_size == 0:
                with msg.loading("saving dump..."), dump_filepath.open(
                    "wb+"
                ) as fd:
                    for data in compress_obj:
                        fd.write(data)
        compress_obj.close()
        with tqdm(desc="wrap up", total=len(fs), disable=tqdm_disable) as pbar:
            for f in as_completed(fs):
                for res in f.result():
                    if not res:
                        continue
                    yield res
                pbar.update(1)
    msg.good(dump_name, show=verbose)


def _get_wiki_dump_obj(wiki_sql_dump_url, verbose):
    if isinstance(wiki_sql_dump_url, Path):
        if not wiki_sql_dump_url.exists():
            raise FileNotFoundError
        compress_obj = wiki_sql_dump_url.open("rb")
        content_len = wiki_sql_dump_url.stat().st_size
        if content_len == 0:
            raise FileNotFoundError
        msg.text(f"found locally at {wiki_sql_dump_url}", show=verbose)
    elif isinstance(wiki_sql_dump_url, URL):
        compress_obj = http_open(str(wiki_sql_dump_url), mode="rb")
        content_len = int(compress_obj.response.headers.get("content-length"))
        msg.text(f"download from: {wiki_sql_dump_url}", show=verbose)
    else:
        raise ValueError
    return compress_obj, content_len


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
