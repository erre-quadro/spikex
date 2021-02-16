# SpikeX - SpaCy Pipes for Knowledge Extraction

SpikeX is a collection of pipes ready to be plugged in a spaCy pipeline.
It aims to help in building knowledge extraction tools with almost-zero effort.

[![Travis Build Status](<https://img.shields.io/travis/erre-quadro/spikex/master.svg?style=flat-square&logo=travis-ci&logoColor=white&label=build+(3.x)>)](https://travis-ci.org/erre-quadro/spikex)
[![pypi Version](https://img.shields.io/pypi/v/spikex.svg?style=flat-square&logo=pypi&logoColor=white)](https://pypi.org/project/spikex/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg?style=flat-square)](https://github.com/ambv/black)

## Features

<<<<<<< HEAD
- ** **NEW** ** Wikipedia graph for entities and categories;
- ** **NEW** ** Knowledge extraction (KEX) pipes;
=======
>>>>>>> master
- **Matcher** based on [spaCy's one](https://github.com/explosion/spaCy/blob/master/spacy/matcher/matcher.pyx) but boosted;
- **Abbreviations** and **acronyms** detector based on [scispacy's one](https://github.com/allenai/scispacy/blob/master/scispacy/abbreviation.py) with improvements;
- **Sentence** splitter based on [Splitta](https://github.com/dgillick/splitta) modernized;

## Install SpikeX

Some requirements are inherited from spaCy:

- **Operating system**: macOS / OS X · Linux · Windows (Cygwin, MinGW, Visual
  Studio)
- **Python version**: Python 3.6+ (only 64 bit)
- **Package managers**: [pip](https://pypi.org/project/spikex/)

### pip

Installing SpikeX via pip is a one line command:

```bash
pip install spikex
```

A virtual environment is always recommended, in order to avoid modifying system state.

## Usage

SpikeX needs a spaCy model to be installed in order to work. Follow spaCy official instructions [here](https://spacy.io/usage/models#download).

### WikiGraph

All KEX pipes has a WikiGraph at their core, which is built starting from some key components of Wikipedia: pages, categories and relations between them. A WikiGraph needs to be created first, before to be used:

```bash
python -m spikex create-wikigraph \
 --wiki <WIKI-NAME, default: en> \
 --version <DUMP-VERSION, default: latest> \
 --output-path <YOUR-OUTPUT-PATH> \
 --dumps-path <DUMPS-BACKUP-PATH> \
 --only-core
```

Then it needs to be packed and installed:

```bash
python -m spikex package-wikigraph \
 --input-path <WIKIGRAPH-RAW-PATH> \
 --output-path <YOUR-OUTPUT-PATH>
```

Follow the instructions at the end of the packing process and install the distribution package in your virtual environment.
Now your are ready to use your WikiGraph as you wish:

```python
from spikex.wikigraph import WikiGraph

wg = WikiGraph.load("enwiki_core")
```

### KEX - CatchX

The **CatchX** pipe uses a WikiGraph in order to find all Wikipedia pages which could relate to chunks in the text.

```python
import spacy
from spikex.wikigraph import WikiGraph
from spikex.kex import CatchX

nlp = spacy.load("en_core_web_sm")
wg = WikiGraph.load("enwiki_core")
nlp.add_pipe(CatchX(graph=wg))
doc = nlp("a little snippet of text")
doc._.catches
```

### KEX - IdentX

The **IdentX** pipe inherits from CatchX all catches found and selects which Wikipedia page fits better for a specific chunk in the text.

```python
import spacy
from spikex.wikigraph import WikiGraph
from spikex.kex import IdentX

nlp = spacy.load("en_core_web_sm")
wg = WikiGraph.load("enwiki_core")
nlp.add_pipe(IdentX(graph=wg))
doc = nlp("a little snippet of text")
doc._.idents
```

### KEX - TopicX

The **TopicX** pipe inherits from IdentX all idents found and uses them in order to retrieve all topics treated in the text.

```python
import spacy
from spikex.wikigraph import WikiGraph
from spikex.kex import TopicX

nlp = spacy.load("en_core_web_sm")
wg = WikiGraph.load("enwiki_core")
nlp.add_pipe(TopicX(graph=wg))
doc = nlp("a little snippet of text")
doc._.catches
```

### KEX - LinkageX

Soon

### Matcher

The **Matcher** is identical to the spaCy's one, but slightly faster, so follow its usage instructions [here](https://spacy.io/usage/rule-based-matching#matcher).

### AbbrX

The **AbbrX** pipe finds abbreviations and acronyms in the text, linking short and long forms together:

```python
import spacy
from spikex.pipes import AbbrX

nlp = spacy.load("en_core_web_sm")
abbrx = AbbrX(nlp)
nlp.add_pipe(abbrx)
doc = nlp("a little snippet with abbreviations (abbrs)")
doc._.abbrs
```

### SentX

The **SentX** pipe splits all text in sentences. It is strongly based on [Splitta](https://github.com/dgillick/splitta). It modifies tokens' *is_sent_start* attribute, so it's mandatory to add it before the parser in the spaCy pipeline:

```python
import spacy
from spikex.pipes import SentX

nlp = spacy.load("en_core_web_sm")
sentx = SentX()
nlp.add_pipe(sentx, before="parser")
doc = nlp("A little sentence. Followed by another one.")
doc.sents
```

## That's all folks
Have fun!
