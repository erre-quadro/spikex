import spacy
from pytest import fixture


@fixture()
def nlp():
    return spacy.load("en_core_web_sm")
