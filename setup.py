#!/usr/bin/env python
import ast
import os
import re

from setuptools import setup


here = os.path.dirname(__file__)
with open(os.path.join(here, "README.rst")) as f:
    readme = f.read()
with open(os.path.join(here, "CHANGES.rst")) as f:
    changelog = f.read()

long_description = readme + "\n\n" + changelog

metadata = {}
with open(os.path.join(here, "ppa_copy_packages.py")) as f:
    rx = re.compile("(__version__|__author__|__url__|__licence__) = (.*)")
    for line in f:
        m = rx.match(line)
        if m:
            metadata[m.group(1)] = ast.literal_eval(m.group(2))
version = metadata["__version__"]

setup(
    name="ppa-copy-packages",
    version=version,
    author="Marius Gedminas",
    author_email="marius@gedmin.as",
    url=metadata["__url__"],
    description="Copy Ubuntu PPA packages from one release pocket to another",
    long_description=long_description,
    long_description_content_type='text/x-rst',
    keywords="ubuntu ppa launchpad copy automation",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Programming Language :: Python :: 3.14",
    ],
    license="GPL-2.0-or-later",
    python_requires=">=3.10",

    py_modules=["ppa_copy_packages"],
    zip_safe=False,
    install_requires=[
        "launchpadlib[keyring]",
    ],
    extras_require={},
    entry_points={
        "console_scripts": [
            "ppa-copy-packages = ppa_copy_packages:main",
        ],
    },
)
