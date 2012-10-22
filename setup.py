#!/usr/bin/env python

from setuptools import setup

setup(name="coursera-dl",
            version="1.1.4",
            description="Download coursera.org class videos and resources",
            long_description=open("README.md").read(),
            author="Dirk Gorissen",
            author_email="dgorissen@gmail.com",
            url="https://github.com/dgorissen/coursera-dl",
            license="GPLv3",
            packages=["courseradownloader"],
            entry_points = { "console_scripts" : [ "coursera-dl = courseradownloader.courseradownloader:main"]},
            install_requires=["mechanize","beautifulsoup4","argparse"],
           )

