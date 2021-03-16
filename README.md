# SpikeX - SpaCy Pipes for Knowledge Extraction

SpikeX is a collection of pipes ready to be plugged in a spaCy pipeline.
It aims to help in building knowledge extraction tools with almost-zero effort.

[![Build Status](https://img.shields.io/azure-devops/build/erre-quadro/spikex/3/master?label=build&logo=azure-pipelines&style=flat-square)](https://dev.azure.com/erre-quadro/spikex/_build/latest?definitionId=3&branchName=master)
[![pypi Version](https://img.shields.io/pypi/v/spikex.svg?style=flat-square&logo=pypi&logoColor=white)](https://pypi.org/project/spikex/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg?style=flat-square)](https://github.com/ambv/black)

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
| 2021-02-01 | enwiki_core | EN | 1.5GB | 9.5GB | [![][dl]][enwiki_core_20210210] | 
| 2021-02-01 | simplewiki_core | EN | 23MB | 183MB | [![][dl]][simplewiki_core_20210210] |
| 2021-02-01 | itwiki_core | IT | 244MB | 1.7GB | [![][dl]][itwiki_core_20210210] |
| More coming... |

[enwiki_core_20210210]: https://errequadrosrl-my.sharepoint.com/:u:/g/personal/paolo_arduin_errequadrosrl_onmicrosoft_com/ESedYiVvufpCtImuOlFXm6MB_5YyfKQnZIvDinnYbL-NmA?Download=1
[simplewiki_core_20210210]: https://errequadrosrl-my.sharepoint.com/:u:/g/personal/paolo_arduin_errequadrosrl_onmicrosoft_com/EQhheXcD9KtGpXyoZ9a2zOEBmGIvZXuyFoV1KoYOzgsjLw?Download=1
[itwiki_core_20210210]: https://errequadrosrl-my.sharepoint.com/:u:/g/personal/paolo_arduin_errequadrosrl_onmicrosoft_com/EVBnV0JaBNlFpmNg91hT458BfFjY_7MW2kqIvRCkhdpWVQ?Download=1

[dl]: http://i.imgur.com/gQvPgr0.png

SpikeX provides a command to shortcut downloading and installing a `WikiGraph`:
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
nlp_vx = wg.find_vertex("Natural_language_processing")
print(nlp["title"])

>>> Natural_language_processing
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
wpx = WikiPagex(wg)
doc = wpx(doc)
for span in doc._.wiki_spans:
  print(span._.wiki_pages)

>>> [(211331, 'An')]
>>> [(31340, 'Apple'), (52207, 'Apple_(disambiguation)'), (53570, 'Apple_(company)'), (235117, 'Apple_(tree)')]
>>> [(31322, 'A'), (135354, 'A_(musical_note)'), (206266, 'A_(New_York_City_Subway_service)'), (211236, 'A_(disambiguation)'), (212629, 'A_(Cyrillic)')]
>>> [(32414, 'Day')]
>>> [(248450, 'The_Doctor'), (248452, 'The_Doctor_(Doctor_Who)'), (248453, 'The_Doctor_(Star_Trek)'), (248519, 'The_Doctor_(disambiguation)')]
>>> [(206763, 'The')]
>>> [(73638, 'Doctor_(Doctor_Who)'), (231571, 'Doctor_(Star_Trek)'), (232311, 'Doctor'), (250762, 'Doctor_(title)'), (262817, 'Doctor_(disambiguation)')]
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
Have fun!
