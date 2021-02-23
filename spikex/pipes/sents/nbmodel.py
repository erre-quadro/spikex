import math
from pathlib import Path
from typing import Dict, List

import regex as re
from wasabi import msg

from spikex.util import pickle_dump, pickle_load

from .fragment import Fragment


class NBModel:
    """
    Naive Bayes model, with a few tweaks:
    - all feature types are pooled together for normalization (this might help
      because the independence assumption is so broken for our features)
    - smoothing: add 0.1 to all counts
    - priors are modified for better performance (this is mysterious but works much better)
    """

    _PRIOR_FEAT = "<prior>"

    def __init__(self):
        self.feats = {}
        self.lower_words = {}
        self.non_abbrs = {}

    @staticmethod
    def load(path: Path = None):
        if path is None:
            path = Path(__file__).parent / "nbmodel.gz"
        data = pickle_load(path)
        model = NBModel()
        model.feats = data["feats"]
        model.lower_words = data["lower_words"]
        model.non_abbrs = data["non_abbrs"]
        return model

    def save(self, path: Path):
        data = {
            "feats": self.feats,
            "lower_words": self.lower_words,
            "non_abbrs": self.non_abbrs,
        }
        pickle_dump(data, path / "nbmodel.gz", compress=True)

    def featurize_one(self, frag: Fragment):
        frag.features = self._get_features(frag)
        return frag.features

    def featurize(self, corpus: List[Fragment]):
        for frag in corpus:
            self.featurize_one(frag)

    def classify_one(self, frag: Fragment):
        # the prior is weird, but it works better this way, consistently
        probs = {
            label: self.feats[label, self._PRIOR_FEAT] ** 4 for label in [0, 1]
        }
        for label in probs:
            if frag.features is None:
                self.featurize_one(frag)
            for feat, val in frag.features.items():
                key = (label, feat + "_" + val)
                if key not in self.feats:
                    continue
                probs[label] *= self.feats[key]
        frag.prediction = _normalize(probs)[1]
        return frag.prediction

    def classify(self, fragments: List[Fragment]):
        for frag in fragments:
            self.classify_one(frag)

    def train(self, corpus: List[Fragment], verbose: bool = None):
        if not corpus:
            raise ValueError
        msg.no_print = not verbose
        with msg.loading("setting things up..."):
            self._setup_training(corpus)
        msg.text("train Naive Bayes model")
        feats = {}
        totals = {}
        for frag in corpus:
            for feat, val in frag.features.items():
                feats[frag.label][feat + "_" + val] += 1
            totals[frag.label] += len(frag.features)
        # add-1 smoothing and normalization
        with msg.loading("smoothing... "):
            smooth_inc = 0.1
            all_feat_names = set(feats[True].keys()).union(
                set(feats[False].keys())
            )
            for label in [0, 1]:
                totals[label] += len(all_feat_names) * smooth_inc
                for feat in all_feat_names:
                    feats[label][feat] += smooth_inc
                    feats[label][feat] /= totals[label]
                    self.feats[(label, feat)] = feats[label][feat]
                feats[label][self._PRIOR_FEAT] = (
                    totals[label] / totals.totalCount()
                )
                self.feats[(label, self._PRIOR_FEAT)] = feats[label][
                    self._PRIOR_FEAT
                ]
        msg.good("done")

    def _setup_training(self, corpus: List[Fragment]):
        self.lower_words, self.non_abbrs = corpus.get_stats(verbose=False)
        self.lower_words = dict(self.lower_words)
        self.non_abbrs = dict(self.non_abbrs)
        self.featurize(corpus)

    def _get_features(self, frag: Fragment):
        # ... w1. (sb?) w2 ...
        # Features, listed roughly in order of importance:
        #   (1) w1: word that includes a period
        #   (2) w2: the next word, if it exists
        #   (3) w1length: number of alphabetic characters in w1
        #   (4) w2cap: true if w2 is capitalized
        #   (5) both: w1 and w2
        #   (6) w1abbr: log count of w1 in training without a final period
        #   (7) w2lower: log count of w2 in training as lowercased
        #   (8) w1w2upper: w1 and w2 is capitalized
        words1 = frag.words(clean=True)
        w1 = words1[-1] if words1 else ""
        words2 = frag.next.words(clean=True) if frag.next else []
        w2 = words2[0] if words2 else ""
        c1 = re.sub(r"(^.+?\-)", "", w1)
        c2 = re.sub(r"(\-.+?)$", "", w2)
        feats = {}
        feats["w1"] = c1
        feats["w2"] = c2
        feats["both"] = c1 + "_" + c2
        len1 = min(10, len(re.sub(r"\W", "", c1)))
        if c1.replace(".", "").isalpha():
            feats["w1length"] = str(len1)
            try:
                feats["w1abbr"] = str(
                    int(math.log(1 + self.non_abbrs[c1[:-1]]))
                )
            except:
                feats["w1abbr"] = str(int(math.log(1)))
        if c2.replace(".", "").isalpha():
            feats["w2cap"] = str(c2[0].isupper())
            try:
                feats["w2lower"] = str(
                    int(math.log(1 + self.lower_words[c2.lower()]))
                )
            except:
                feats["w2lower"] = str(int(math.log(1)))
            feats["w1w2upper"] = c1 + "_" + str(c2[0].isupper())
        return feats


def _normalize(counter: Dict[str, float]):
    # normalize a counter by dividing each value by the sum of all values
    total = float(sum(counter.values()))
    return {k: v / total for k, v in counter.items()}
