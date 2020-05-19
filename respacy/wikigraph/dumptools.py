from concurrent.futures import ProcessPoolExecutor, as_completed
from functools import partial

from ftfy import fix_text
from smart_open.compression import compression_wrapper
from smart_open.http import open as http_open
from tqdm import tqdm
from yarl import URL

from .. import data

__all__ = [
    "get_pageid_title_map",
    "get_categoryid_title_map",
    "get_redirectid_target_map",
    "get_categories_linking_map",
]

_WIKI_DP_PAGE = "page"
_WIKI_DP_REDIRECT = "redirect"
_WIKI_DP_CATEGORYLINKS = "categorylinks"
_WIKI_DL_NAME = "{l}wiki-{v}-{t}.sql.gz"
_WIKI_DL_PATH = "https://dumps.wikimedia.org/{l}wiki/{v}/{n}"


def get_pageid_title_map(l, v):
    dump_url = _get_wiki_dump_dl_url(l, _WIKI_DP_PAGE, v)
    return _parse_wiki_sql_dump(dump_url, _parse_fx_pageid_title_map)


def _parse_fx_pageid_title_map(el):
    if el[1] != "0":
        return
    pageid = int(el[0])
    title = fix_text(el[2])
    return pageid, title


def get_categoryid_title_map(l, v):
    dump_url = _get_wiki_dump_dl_url(l, _WIKI_DP_PAGE, v)
    return _parse_wiki_sql_dump(dump_url, _parse_fx_categoryid_title_map)


def _parse_fx_categoryid_title_map(el):
    if el[1] != "14":
        return
    pageid = int(el[0])
    title = fix_text(el[2])
    return pageid, title


def get_redirectid_target_map(l, v):
    dump_url = _get_wiki_dump_dl_url(l, _WIKI_DP_REDIRECT, v)
    return _parse_wiki_sql_dump(dump_url, _parse_fx_redirectid_target_map)


def _parse_fx_redirectid_target_map(el):
    if el[1] not in ("0", "14"):
        return
    redirectid = int(el[0])
    title = fix_text(el[2])
    return redirectid, title


def get_categories_linking_map(l, v):
    dump_url = _get_wiki_dump_dl_url(l, _WIKI_DP_CATEGORYLINKS, v)
    return _parse_wiki_sql_dump(dump_url, _parse_fx_categories_linking_map)


def _parse_fx_categories_linking_map(el):
    if el[6] not in ("page", "subcat"):
        return
    sourceid = int(el[0])
    target = fix_text(el[1])
    return sourceid, target


def _get_wiki_dump_dl_url(l, t, v):
    n = _WIKI_DL_NAME.format(l=l, t=t, v=v)
    return URL(_WIKI_DL_PATH.format(l=l, n=n, v=v))


def _parse_wiki_sql_dump(wiki_sql_dump_url, parse_fx):
    with ProcessPoolExecutor(max_workers=4) as executor:
        fs = []
        mode = "rb"
        compress_bytes_read = 0
        if data.contains(wiki_sql_dump_url.name):
            compress_obj = data.open(wiki_sql_dump_url.name, mode=mode)
            content_len = data.force_get(wiki_sql_dump_url.name).stat().st_size
        else:
            compress_obj = http_open(str(wiki_sql_dump_url), mode=mode)
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
                        if not isinstance(d[k], list):
                            d[k] = [d[k]]
                        d[k].append(v)
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
