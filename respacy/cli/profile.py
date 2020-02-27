import cProfile
import pstats
from pathlib import Path
from random import shuffle

import plac
import spacy
from srsly import read_jsonl
from tqdm import tqdm
from wasabi import msg

from ..matcher import REMatcher

resources_path = Path("resources")


@plac.annotations()
def profile():
    from spacy.matcher import Matcher
    sample_doc = doc()
    # matcher = Matcher(sample_doc.vocab)  
    matcher = REMatcher(sample_doc.vocab)
    for p in patterns():
        try:
            matcher.add("Profile", [p])
        except:
            pass
    cProfile.runctx(
        "matches(matcher, sample_doc)", globals(), locals(), "Profile.prof"
    )
    s = pstats.Stats("Profile.prof")
    msg.divider("Profile stats")
    s.strip_dirs().sort_stats("cumtime").print_stats()


def matches(matcher, doc):
    with tqdm(total=len(patterns())) as pbar:
        last = 0
        for match in tqdm(matcher(doc)):
            pbar.update(match[1] - last)


def patterns():
    patterns_path = resources_path.joinpath("patterns.jsonl")
    pttrns = list(read_jsonl(patterns_path))
    # shuffle(pttrns)
    return pttrns[28720:31288]


def patterns_test():
    raw = [
        "[\\s\\S]+",
        "[\\s\\S]+",
        "(?:\\b[Rr][Uu][Nn]\\b)",
        "[\\s\\S]+",
        "(?:\\b[Ww][Aa][Tt][Ee][Rr]\\b) ?(?:\\b[Tt][Aa][Nn][Kk]\\b)",
        "[\\s\\S]+",
        "[\\s\\S]+",
        "[\\s\\S]+",
        "(?:\\b[Rr][Ee][Ss][Tt][Rr][Aa][Ii][Nn][Ii][Nn][Gg]\\b)",
        "(?:\\b[Ff][Ll][Aa][Rr][Ee][Ss]\\b)",
        "[\\s\\S]+",
        "[\\s\\S]+",
    ]

    return [[{"REGEX": v}] for v in raw]


def doc():
    return spacy.load("en_core_web_sm")(
        open(resources_path.joinpath("sample.txt"), "r").read()
    )
