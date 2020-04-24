import cProfile
import pstats
from pathlib import Path

import plac
import spacy
from spacy.matcher import Matcher as _Matcher
from srsly import read_jsonl
from wasabi import msg

from ..matcher._matcher import Matcher


@plac.annotations()
def profile(patterns_path, matcher: str = None):
    sample_doc = doc()
    matcher = (
        _Matcher(sample_doc.vocab)
        if matcher == "spacy"
        else Matcher(sample_doc.vocab)
    )
    # patterns = [
    #     [{"LOWER": {"IN": ["tether"]}}, {"LOWER": {"IN": ["arrangement"]}, "POS": {"IN": ["NOUN"]}}],
    #     [{"LOWER": {"IN": ["tether"]}}, {"LOWER": {"IN": ["hinge"]}, "POS": {"IN": ["NOUN"]}}]
    # ]

    # pattern = [
    #     {"POS": {"NOT_IN": ["NOUN", "ADJ", "ADV"]}},
    #     {"LOWER": {"IN": ["means"]}, "POS": {"IN": ["NOUN"]}},
    #     {"LEMMA": {"IN": ["for", "to"]}},
    #     {"POS": {"IN": ["NOUN", "ADJ", "ADV", "VERB"]}},
    # ]

    matcher.add("Profile", patterns(patterns_path))
    cProfile.runctx(
        "matches(matcher, sample_doc)", globals(), locals(), "Profile.prof"
    )
    s = pstats.Stats("Profile.prof")
    msg.divider("Profile stats")
    s.strip_dirs().sort_stats("time").print_stats()


def matches(matcher, doc):
    count = 0
    for _, s, e in matcher(doc):
        count += 1
        print(doc[s:e], s, e)
    msg.text("Total matches", count)


def patterns(patterns_path):
    return list(
        [
            p["pattern"] if "pattern" in p else p
            for p in read_jsonl(patterns_path)
        ]
    )


def doc():
    return spacy.load("en_core_web_sm")(
        open(Path("resources").joinpath("sample.txt"), "r").read()
    )
