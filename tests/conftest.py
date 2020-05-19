import pytest
import spacy
from spacy.util import get_lang_class


def pytest_addoption(parser):
    parser.addoption(
        "--slow", action="store_true", default=False, help="include slow tests"
    )


@pytest.fixture(scope="module")
def nlp():
    return spacy.load("en_core_web_sm")


@pytest.fixture(scope="session")
def en_vocab():
    return get_lang_class("en").Defaults.create_vocab()


@pytest.fixture(scope="session")
def en_tokenizer():
    return get_lang_class("en").Defaults.create_tokenizer()
