#!/usr/bin/env python

from setuptools import setup
from os import path
import os
import version


# get the requirements from the pip requirements file
requirements = []

with open("requirements.txt") as f:
    for l in f:
        l = l.strip()
        if l: requirements.append(l)

setup(name="coursera-dl",
            version=version.VERSION,
            description="Download coursera.org class videos and resources",
            long_description=open("README.md").read(),
            author="Dirk Gorissen",
            author_email="dgorissen@gmail.com",
            url="https://github.com/dgorissen/coursera-dl",
            license="GPLv3",
            packages=["courseradownloader"],
            py_modules=['version'],  
            entry_points = { "console_scripts" : [ "coursera-dl = courseradownloader.courseradownloader:main"]},
            install_requires=requirements
           )

