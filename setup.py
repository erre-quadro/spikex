from setuptools import setup, find_packages

with open("README.md") as readme_file:
    readme = readme_file.read()

requirements = [
    "cython",
    "cyac",
    "ftfy",
    "jsonschema",
    "memory_profiler",
    "python-igraph",
    "regex",
    "smart-open",
    "spacy>=2.2.2,<3.0",
    "typer",
    "wasabi",
    "yarl",
]

setup_requirements = ["pytest-runner"]

test_requirements = ["pytest"]

setup(
    author="Erre Quadro srl",
    author_email="paolo.arduin@errequadrosrl.com",
    python_requires=">=3.6",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache Software License",
        "Natural Language :: English",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
    ],
    description="SPIKEX - SpaCy Pipes for Knowledge Extraction",
    install_requires=requirements,
    license="Apache Software License 2.0",
    long_description=readme,
    include_package_data=True,
    keywords="spikex",
    name="spikex",
    packages=find_packages(include=["spikex", "spikex.*"]),
    setup_requires=setup_requirements,
    test_suite="tests",
    tests_require=test_requirements,
    url="https://github.com/erre-quadro/spikex",
    version="0.4.0-dev2",
    zip_safe=False,
)
