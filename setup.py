#!/usr/bin/env python

"""The setup script."""

from setuptools import setup, find_packages

with open("README.md") as readme_file:
    readme = readme_file.read()

with open("HISTORY.rst") as history_file:
    history = history_file.read()

requirements = [
    "jsonschema",
    "regex",
    "spacy>=2.2.2",
    "wasabi",
    "typer"
]

setup_requirements = ["pytest-runner"]

test_requirements = ["pytest"]

setup(
    author="Paolo Arduin",
    author_email="paolo.arduin@errequadrosrl.com",
    python_requires=">=3.6",
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache Software License",
        "Natural Language :: English",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
    ],
    description="🌀A set of custom pipes which enhance and exploit spaCy.",
    install_requires=requirements,
    license="Apache Software License 2.0",
    long_description=readme + "\n\n" + history,
    include_package_data=True,
    keywords="respacy",
    name="respacy",
    packages=find_packages(include=["respacy", "respacy.*"]),
    setup_requires=setup_requirements,
    test_suite="tests",
    tests_require=test_requirements,
    url="https://github.com/erre-quadro/respacy",
    version="0.1.2-dev1",
    zip_safe=False,
)
