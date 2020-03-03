# 🌀 RespaCy

This repository contains a set of pipes which exploit and enhance spaCy in matching, labelling and linking textual entities.

## Installation

*SOON* - Install package from PyPI:
```bash
pip install spacy
```

Install from GitHub:
```bash
pip install git+https://github.com/erre-quadro/respacy.git
```

## Features

### AbbreviationDetector
A detector of abbreviations based on the scispaCy [AbbreviationDetector](https://github.com/allenai/scispacy#abbreviationdetector), enhanced to recognize abbreviations not in brackets and to prioritize acronyms.

### REMatcher
A pattern matching detector based on the logic of the spaCy [Matcher](https://spacy.io/usage/rule-based-matching), enhanced with a matching multilayer which use the *RegEx* power to increase performance and patterns expressiveness.


### Labeller
A *REMatcher* exploitation for labelling text chunks based on patterns.

## Benchmark

*SOON*
