---
layout: single
title:  "Setting up and Debugging Editable Python Packages"
tags:
  - documentation
---

Editable installs in Python are kind of broken, at least in more recent versions of Python 3 (~3.7+ at least). The purpose of an editable installation is to allow the developer of a package to install and import it in the same fashion that any user would, and enable changes to be made to the installed package without needing to reinstall the package after every single change. Unfortunately, that functionality seems to be broken, at least using `pip` and `venv`. 

Editable packages can be successfully installed using `pip install -e <package_name>`, but attempting to import them will result in a `ModuleNotFoundError`.

# Installing Editable Packages
There are two main use cases for editable packages: testing the package under development, and testing another package under development.

## Debugging a Package Under Development
In this case, I would run `pip install .` to install the package that I am developing in my current directory (typically within a `package_folder/src` or `package_folder/src/package_name` folder) into the virtual environment of that current directory. Once installed, a test (likely located in a `package_folder/tests` folder) can use the package just like any other to test its functionality:
```python
import my_package

assert my_package.example_function() == 1
```

## Debugging Another Package Under Development
In this case, I am actively developing Package B, which depends on Package A, which is a second package that I have developed. Assuming that I have uploaded Package A to PyPI, I can install it just like any other package: `pip install package_a`. However, often Package A may need some additions or modifications to get Package B working. In that case, I don't want to have to reupload to PyPI and reinstall using pip every time I change Package A.

### Editable Install From Local Folder
Running `pip install -e <package_a_folder>` in the Package B folder, where `<package_a_folder>` is the absolute or relative path to the package directory, should create an editable installation of Package A in the Package B virtual environment. This is the optimal setup, because changes to Package A in its own folder will be reflected in Package B immediately, without any additional steps.

### Non-Editable Install From Local Folder
However, editable installs frequently result in broken import statements, with Python reporting a `ModuleNotFoundError`. If that happens, you can work around it by simply removing the editable part of the command and running `pip install <package_a_folder>`. This should fix these errors, and allow you to use Package A just like anyone else would. However, any changes made to Package A will not appear in Package B until you re-run the `pip install` command.