# Contributing

Contributions are welcome, and they are greatly appreciated! Every little bit
helps, and credit will always be given.

You can contribute in many ways:

## Types of Contributions

### Report Bugs

Report bugs at [https://github.com/erre-quadro/spikex/issues](https://github.com/erre-quadro/spikex/issues).

If you are reporting a bug, please include:

* Your operating system name and version.
* Any details about your local setup that might be helpful in troubleshooting.
* Detailed steps to reproduce the bug.

### Fix Bugs


Look through the GitHub issues for bugs. Anything tagged with "bug" and "help
wanted" is open to whoever wants to implement it.

### Implement Features

Look through the GitHub issues for features. Anything tagged with "enhancement"
and "help wanted" is open to whoever wants to implement it.

### Write Documentation

SpikeX could always use more documentation, whether as part of the
official spikex docs, in docstrings, or even on the web in blog posts,
articles, and such.

### Submit Feedback

The best way to send feedback is to file an issue at [https://github.com/erre-quadro/spikex/issues](https://github.com/erre-quadro/spikex/issues).

If you are proposing a feature:

* Explain in detail how it would work.
* Keep the scope as narrow as possible, to make it easier to implement.
* Remember that this is a volunteer-driven project, and that contributions
  are welcome :)

## Get Started!

Ready to contribute? Here's how to set up `spikex` for local development.

1. Fork the `spikex` repo on GitHub
2. Clone your fork locally:
    ```bash
    git clone git@github.com:your_name_here/spikex.git
    ```

3. Install and setup a virtualenv in your local copy:
    ```bash
    cd spikex/
    ./scripts/create-venv.sh
    . .venv/bin/activate
    ```

4. Create a branch for local development:
    ```bash
    git checkout -b name-of-your-bugfix-or-feature
    ```

   Now you can make your changes locally.

5. When you're done making changes, please format your code and check that your changes pass all
   tests:
   ```bash
   invoke format
   invoke test
   ```

6. Commit your changes and push your branch to GitHub:
    ```bash
    git add .
    git commit -m "Your detailed description of your changes."
    git push origin name-of-your-bugfix-or-feature
    ```

7. Submit a pull request through [GitHub](https://github.com/erre-quadro/spikex/pulls).

## Pull Request Guidelines

Before you submit a pull request, check that it meets these guidelines:

1. The pull request should include tests.
2. If the pull request adds functionality, the docs should be updated. Put
   your new functionality into a function with a docstring, and add the
   feature to the list in README.md.
3. The pull request should work for Python 3.6, 3.7, 3.8, and 3.9. It must pass tests for all supported Python versions.
