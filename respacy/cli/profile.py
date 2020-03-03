import cProfile
import pstats

import plac
import spacy
from srsly import read_jsonl
from tqdm import tqdm
from wasabi import msg

from ..matcher import REMatcher


@plac.annotations()
def profile(patterns_path):
    sample_doc = doc()
    # matcher = Matcher(sample_doc.vocab)
    matcher = REMatcher()
    matcher.add("Profile", patterns(patterns_path))
    cProfile.runctx(
        "matches(matcher, sample_doc)", globals(), locals(), "Profile.prof"
    )
    s = pstats.Stats("Profile.prof")
    msg.divider("Profile stats")
    s.strip_dirs().sort_stats("time").print_stats()


def matches(matcher, doc):
    with tqdm(total=len(matcher)) as pbar:
        last = 0
        for match in tqdm(matcher(doc)):
            pbar.update(match[1] - last)


def patterns(patterns_path):
    return list(read_jsonl(patterns_path))


def doc():
    return spacy.load("en_core_web_sm")(
        open(resources_path.joinpath("sample.txt"), "r").read()
    )
