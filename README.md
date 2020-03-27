# 🌀 RespaCy

This repository contains a set of pipes which exploit and enhance spaCy in matching, labeling and linking textual entities.

## Installation

*SOON - Install package from PyPI:*
```bash
pip install respacy
```

Install from GitHub:
```bash
pip install git+https://github.com/erre-quadro/respacy.git
```

## Features

### AbbreviationDetector
A revisited version of the scispaCy [AbbreviationDetector](https://github.com/allenai/scispacy#abbreviationdetector), enhanced to recognize better abbreviations and acronyms, as well as to relate them to their extended form in a more detailed way.

### Labeler
A *Matcher* exploitation for labeling text chunks based on patterns. 

### Matcher
A pattern matching detector based on the logic of the spaCy [Matcher](https://spacy.io/usage/rule-based-matching), enhanced with a matching layer which use the *RegEx* power to increase performance and patterns expressiveness.

## Benchmark

*SOON*
