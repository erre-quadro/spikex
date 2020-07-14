from setuptools import setup, find_packages

with open("README.md") as readme_file:
    readme = readme_file.read()

requirements = [
    "jsonschema",
    "regex",
    "spacy>=2.2.2,<3.0",
    "wasabi",
    "typer",
]

setup_requirements = ["pytest-runner"]

test_requirements = ["pytest"]

setup(
    author="Erre Quadro srl",
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
    description="SPIKE - SpaCy Pipes for Knowledge Extraction",
    install_requires=requirements,
    license="Apache Software License 2.0",
    long_description=readme,
    include_package_data=True,
    keywords="spike",
    name="spike",
    packages=find_packages(include=["spike", "spike.*"]),
    setup_requires=setup_requirements,
    test_suite="tests",
    tests_require=test_requirements,
    url="https://github.com/erre-quadro/spike",
    version="0.2.2-dev1",
    zip_safe=False,
)
