from functools import partial
from pathlib import Path
from sys import stdout

import spacy
import memory_profiler as mp
from srsly import read_jsonl

from ..matcher import Matcher
from ..wikigraph import WikiGraph

from cProfile import Profile
import pstats


def profile_matcher(patterns_path: str, memory: bool = None):
    def func():
        nlp = spacy.load("en_core_web_sm")
        path = Path("resources") / "sample.txt"
        doc = nlp(path.read_text())
        matcher = Matcher(doc.vocab)
        patterns = [
            p["pattern"] if "pattern" in p else p
            for p in read_jsonl(patterns_path)
        ]
        matcher.add("Profile", patterns)
        matcher(doc)
    
    _profile(func, memory)


def profile_wikigraph_load(graph_name: str, memory: bool = None):
    def func():
        _ = _load_wikigraph(graph_name)

    _profile(func, memory)


def profile_wikigraph_exec(graph_name: str, memory: bool = None):
    wg = _load_wikigraph(graph_name)
    text = """
    Hong Kong (CNN) China's top military commander in Hong Kong has emphasized the role of the People's Liberation Army (PLA) in upholding "national sovereignty" in the city a day ahead of expected anti-government protests.

    Chen Daoxiang, the PLA commander in Hong Kong, was speaking days after China announced plans to introduce a draconian new national security law which threatens many of the semi-autonomous city's civil liberties and political freedoms.
    "Garrison officers and soldiers are determined, confident, and capable of safeguarding national sovereignty and development interests and the long-term prosperity and stability of Hong Kong," Chen said Tuesday, adding that the Hong Kong Garrison viewed the national security law as "conducive to deter separatist forces and external intervention."
    Almost every official department in Hong Kong has issued statements of support for the proposed law this week -- from the police to the fire department and the Government Flying Service. The PLA Garrison has also made similar statements about its role in the past.
    Chen's words do carry some extra weight, however, given the uneasy status of the PLA in the city.
    """

    def func():
        for _ in wg.find_all_pages(text):
            pass
    
    _profile(func, memory)


def _load_wikigraph(graph_name):
    return WikiGraph.load(graph_name=graph_name)


def _profile(fn, memory=None):
    if memory:
        _mem_profile(fn)
    else:
        _time_profile(fn)


def _mem_profile(fn):
    prof = mp.LineProfiler(backend="psutil")
    prof(fn)()
    mp.show_results(prof)


def _time_profile(fn):
    profiler = Profile()
    profiler.runcall(fn)
    stats = pstats.Stats(profiler)        
    stats.sort_stats("time")
    stats.print_stats(40)
