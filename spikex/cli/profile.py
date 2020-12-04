import cProfile
import pstats
from pathlib import Path

import spacy
from spacy.matcher import Matcher as SpacyMatcher
from srsly import read_jsonl
from wasabi import msg

from ..matcher import Matcher


def profile(patterns_path, use_spacy: bool = None):
    sample_doc = get_doc()
    matcher = (SpacyMatcher(sample_doc.vocab)
               if use_spacy else Matcher(sample_doc.vocab))
    matcher.add("Profile", get_patterns(patterns_path))
    cProfile.runctx("exec_match(matcher, sample_doc)", globals(), locals(),
                    "Profile.prof")
    s = pstats.Stats("Profile.prof")
    msg.divider("Profile stats")
    s.strip_dirs().sort_stats("time").print_stats()


def exec_match(matcher, doc):
    count = sum(1 for _ in matcher(doc))
    msg.text(f"Total matches: {count}")


def get_patterns(patterns_path):
    return list([
        p["pattern"] if "pattern" in p else p
        for p in read_jsonl(patterns_path)
    ])


def get_doc():
    return spacy.load("en_core_web_sm")(open(
        Path("resources").joinpath("sample.txt"), "r").read())
