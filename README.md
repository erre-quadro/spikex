# SpikeX - SpaCy Pipes for Knowledge Extraction

SpikeX is a collection of pipes ready to be plugged in a spaCy pipeline.
It aims to help in building knowledge extraction tools with almost-zero effort.

[![Build Status](https://img.shields.io/azure-devops/build/erre-quadro/spikex/3/master?label=build&logo=azure-pipelines&style=flat-square)](https://dev.azure.com/erre-quadro/spikex/_build/latest?definitionId=3&branchName=master)
[![pypi Version](https://img.shields.io/pypi/v/spikex.svg?style=flat-square&logo=pypi&logoColor=white)](https://pypi.org/project/spikex/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg?style=flat-square)](https://github.com/ambv/black)

## What's new in SpikeX 0.5.0

**WikiGraph** has never been so lightning fast:
- 🌕 **Performance mooning**, thanks to the adoption of a *sparse adjacency matrix* to handle pages graph, instead of using *igraph*
- 🚀 **Memory optimization**, with a consumption cut by ~40% and a compressed size cut by ~20%, introducing new *bidirectional dictionaries* to manage data
- 📖 **New APIs** for a faster and easier usage and interaction
- 🛠 **Overall fixes**, for a better graph and a better pages matching 
 
## Pipes

- **WikiPageX** links Wikipedia pages to chunks in text
- **ClusterX** picks noun chunks in a text and clusters them based on a revisiting of the [Ball Mapper](https://arxiv.org/abs/1901.07410) algorithm, Radial Ball Mapper
- **AbbrX** detects abbreviations and acronyms, linking them to their long form. It is based on [scispacy](https://github.com/allenai/scispacy/blob/master/scispacy/abbreviation.py)'s one with improvements
- **LabelX** takes labelings of pattern matching expressions and catches them in a text, solving overlappings, abbreviations and acronyms
- **PhraseX** creates a `Doc`'s underscore extension based on a custom attribute name and phrase patterns. Examples are **NounPhraseX** and **VerbPhraseX**, which extract noun phrases and verb phrases, respectively
- **SentX** detects sentences in a text, based on [Splitta](https://github.com/dgillick/splitta) with refinements

## Tools

- **WikiGraph** with pages as leaves linked to categories as nodes
- **Matcher** that inherits its interface from the [spaCy](https://github.com/explosion/spaCy/blob/master/spacy/matcher/matcher.pyx)'s one, but built using an engine made of RegEx which boosts its performance

## Install SpikeX

Some requirements are inherited from spaCy:

- **spaCy version**: 2.3+
- **Operating system**: macOS / OS X · Linux · Windows (Cygwin, MinGW, Visual
  Studio)
- **Python version**: Python 3.6+ (only 64 bit)
- **Package managers**: [pip](https://pypi.org/project/spikex/)

Some dependencies use **Cython** and it needs to be installed before SpikeX:

```bash
pip install cython
```

Remember that a virtual environment is always recommended, in order to avoid modifying system state.
### pip

At this point, installing SpikeX via pip is a one line command:

```bash
pip install spikex
```

## Usage

### Prerequirements

SpikeX pipes work with spaCy, hence a model its needed to be installed. Follow official instructions [here](https://spacy.io/usage/models#download). The brand new spaCy 3.0 is supported!

### WikiGraph

A `WikiGraph` is built starting from some key components of Wikipedia: *pages*, *categories* and *relations* between them. 

#### Auto

Creating a `WikiGraph` can take time, depending on how large is its Wikipedia dump. For this reason, we provide wikigraphs ready to be used:

| Date | WikiGraph | Lang | Size (compressed) | Size (memory) | |
| --- | --- | --- | --- | --- | --- |
| 2021-04-01 | enwiki_core | EN | 1.3GB | 8GB | [![][dl]][enwiki_core_20210401] | 
| 2021-04-01 | simplewiki_core | EN | 20MB | 128MB | [![][dl]][simplewiki_core_20210401] |
| 2021-04-01 | itwiki_core | IT | 208MB | 1.2GB | [![][dl]][itwiki_core_20210401] |
| More coming... |

[enwiki_core_20210401]: https://errequadrosrl-my.sharepoint.com/:u:/g/personal/paolo_arduin_errequadrosrl_onmicrosoft_com/Eco6n99fPu5NktUaF7SkzpkBk7Ru3ZaH-BD_tr8Tq6sHWw?Download=1
[simplewiki_core_20210401]: https://errequadrosrl-my.sharepoint.com/:u:/g/personal/paolo_arduin_errequadrosrl_onmicrosoft_com/EbwV-u0YtVdNo4f02X7HbDsBs3BRTEu4ix-_n0JYLKOJzQ?Download=1
[itwiki_core_20210401]: https://errequadrosrl-my.sharepoint.com/:u:/g/personal/paolo_arduin_errequadrosrl_onmicrosoft_com/EY7anrn0R0JApoIryZck2b0Bl6T_o3YGNAbCpg6eAHXPrg?Download=1

[dl]: http://i.imgur.com/gQvPgr0.png

SpikeX provides a command to shortcut downloading and installing a `WikiGraph` (Linux or macOS, Windows not supported yet):
```bash
spikex download-wikigraph simplewiki_core
```

#### Manual

A `WikiGraph` can be created from command line, specifying which Wikipedia dump to take and where to save it:

```bash
spikex create-wikigraph \
  <YOUR-OUTPUT-PATH> \
  --wiki <WIKI-NAME, default: en> \
  --version <DUMP-VERSION, default: latest> \
  --dumps-path <DUMPS-BACKUP-PATH> \
```

Then it needs to be packed and installed:

```bash
spikex package-wikigraph \
  <WIKIGRAPH-RAW-PATH> \
  <YOUR-OUTPUT-PATH>
```

Follow the instructions at the end of the packing process and install the distribution package in your virtual environment.
Now your are ready to use your WikiGraph as you wish:

```python
from spikex.wikigraph import load as wg_load

wg = wg_load("enwiki_core")
page = "Natural_language_processing"
categories = wg.get_categories(page, distance=1)
for category in categories:
    print(category)

>>> Category:Speech_recognition
>>> Category:Artificial_intelligence
>>> Category:Natural_language_processing
>>> Category:Computational_linguistics

```
### Matcher

The **Matcher** is identical to the spaCy's one, but faster when it comes to handle many patterns at once (order of thousands), so follow official usage instructions [here](https://spacy.io/usage/rule-based-matching#matcher).

A trivial example:
```python
from spikex.matcher import Matcher
from spacy import load as spacy_load

nlp = spacy_load("en_core_web_sm")
matcher = Matcher(nlp.vocab)
matcher.add("TEST", [[{"LOWER": "nlp"}]])
doc = nlp("I love NLP")
for _, s, e in matcher(doc):
  print(doc[s: e])

>>> NLP
```

### WikiPageX

The `WikiPageX` pipe uses a `WikiGraph` in order to find chunks in a text that match Wikipedia page titles.

``` python
from spacy import load as spacy_load
from spikex.wikigraph import load as wg_load
from spikex.pipes import WikiPageX

nlp = spacy_load("en_core_web_sm")
doc = nlp("An apple a day keeps the doctor away")
wg = wg_load("simplewiki_core")
wpx = WikiPageX(wg)
doc = wpx(doc)
for span in doc._.wiki_spans:
  print(span._.wiki_pages)

>>> ['An']
>>> ['Apple', 'Apple_(disambiguation)', 'Apple_(company)', 'Apple_(tree)']
>>> ['A', 'A_(musical_note)', 'A_(New_York_City_Subway_service)', 'A_(disambiguation)', 'A_(Cyrillic)')]
>>> ['Day']
>>> ['The_Doctor', 'The_Doctor_(Doctor_Who)', 'The_Doctor_(Star_Trek)', 'The_Doctor_(disambiguation)']
>>> ['The']
>>> ['Doctor_(Doctor_Who)', 'Doctor_(Star_Trek)', 'Doctor', 'Doctor_(title)', 'Doctor_(disambiguation)']
``` 

### ClusterX

The `ClusterX` pipe takes noun chunks in a text and clusters them using a Radial Ball Mapper algorithm.

``` python
from spacy import load as spacy_load
from spikex.pipes import ClusterX

nlp = spacy_load("en_core_web_sm")
doc = nlp("Grab this juicy orange and watch a dog chasing a cat.")
clusterx = ClusterX(min_score=0.65)
doc = clusterx(doc)
for cluster in doc._.cluster_chunks:
  print(cluster)

>>> [this juicy orange]
>>> [a cat, a dog]
```

### AbbrX

The **AbbrX** pipe finds abbreviations and acronyms in the text, linking short and long forms together:

```python
from spacy import load as spacy_load
from spikex.pipes import AbbrX

nlp = spacy_load("en_core_web_sm")
doc = nlp("a little snippet with an abbreviation (abbr)")
abbrx = AbbrX(nlp.vocab)
doc = abbrx(doc)
for abbr in doc._.abbrs:
  print(abbr, "->", abbr._.long_form)

>>> abbr -> abbreviation
```

### LabelX

The `LabelX` pipe matches and labels patterns in text, solving overlappings, abbreviations and acronyms.

```python
from spacy import load as spacy_load
from spikex.pipes import LabelX

nlp = spacy_load("en_core_web_sm")
doc = nlp("looking for a computer system engineer")
patterns = [
  [{"LOWER": "computer"}, {"LOWER": "system"}],
  [{"LOWER": "system"}, {"LOWER": "engineer"}],
]
labelx = LabelX(nlp.vocab, ("TEST", patterns), validate=True, only_longest=True)
doc = labelx(doc)
for labeling in doc._.labelings:
  print(labeling, f"[{labeling.label_}]")

>>> computer system engineer [TEST]
```

### PhraseX

The `PhraseX` pipe creates a custom `Doc`'s underscore extension which fulfills with matches from phrase patterns.

```python
from spacy import load as spacy_load
from spikex.pipes import PhraseX

nlp = spacy_load("en_core_web_sm")
doc = nlp("I have Melrose and McIntosh apples, or Williams pears")
patterns = [
  [{"LOWER": "mcintosh"}],
  [{"LOWER": "melrose"}],
]
phrasex = PhraseX(nlp.vocab, "apples", patterns)
doc = phrasex(doc)
for apple in doc._.apples:
  print(apple)

>>> Melrose
>>> McIntosh
```
### SentX

The **SentX** pipe splits sentences in a text. It modifies tokens' *is_sent_start* attribute, so it's mandatory to add it before *parser* pipe in the spaCy pipeline:

```python
from spacy import load as spacy_load
from spikex.pipes import SentX
from spikex.defaults import spacy_version

if spacy_version >= 3:
  from spacy.language import Language

  @Language.factory("sentx")
  def create_sentx(nlp, name):
      return SentX()

nlp = spacy_load("en_core_web_sm")
sentx_pipe = SentX() if spacy_version < 3 else "sentx"
nlp.add_pipe(sentx_pipe, before="parser")
doc = nlp("A little sentence. Followed by another one.")
for sent in doc.sents:
  print(sent)

>>> A little sentence.
>>> Followed by another one.
```

## That's all folks
Feel free to contribute and have fun!
