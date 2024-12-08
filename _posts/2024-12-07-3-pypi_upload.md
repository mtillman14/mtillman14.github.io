---
layout: single
title:  "How to upload Python packages to PyPI"
# categories: 
#   - Jekyll
tags:
  - documentation
---

Instructions for uploading a Python package to [PyPI](https://pypi.org) or [Test PyPI](https://test.pypi.org), taken from [the Python docs](https://packaging.python.org/en/latest/tutorials/packaging-projects/). Note that first you need to have a properly formatted `pyproject.toml` or `setup.py`

# Test PyPI
## Upload to Test PyPI
1. Remove all files from the `dist/` folder before building the package: `rm -rf dist/`

2. Build the package. The version number must be updated (unique) before running the following commands. All actions are performed in the command line from the root directory of the project.
```bash
python3 -m pip install --upgrade build
python3 -m build
python3 -m pip install --upgrade twine
```

3. Upload the package to Test PyPI
```bash
python3 -m twine upload --repository testpypi dist/*
```

## Install from Test PyPI
- Install the package from Test PyPI but installs any dependencies from the **main PyPI** repository: `python -m pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple <package_name>`

OR

- Install the package only from the **Test PyPI** repository: `python3 -m pip install --index-url https://test.pypi.org/simple/ --no-deps <package_name>`

# PyPI
## Upload to PyPI
1. Remove all files from the `dist/` folder before building the package: `rm -rf dist/`

2. Build the package. The version number must be updated (unique) before running the following commands. All actions are performed in the command line from the root directory of the project.
```bash
python3 -m pip install --upgrade build
python3 -m build
python3 -m pip install --upgrade twine
```

3. Upload the package to PyPI: `python3 -m twine upload dist/*`

## Install from PyPI
1. `python3 -m pip install <package_name>`