from setuptools import setup, find_packages

with open("README.md") as readme_file:
    readme = readme_file.read()

requirements = open("requirements.txt").read().splitlines()

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
    long_description_content_type="text/markdown",
    include_package_data=True,
    keywords="spikex",
    name="spikex",
    packages=find_packages(include=["spikex", "spikex.*"]),
    test_suite="tests",
    tests_require=test_requirements,
    url="https://github.com/erre-quadro/spikex",
    version="0.5.1",
    zip_safe=False,
    entry_points = {
        'console_scripts': ['spikex=spikex.__main__:main'],
    }
)
