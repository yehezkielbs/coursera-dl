#!/usr/bin/env python

from distutils.core import setup

setup(name='coursera-dl',
            version='1.0',
            description='Coursera downloader',
            author='Dirk Gorissen',
            author_email='dgorissen@gmail.com',
            url='https://github.com/dgorissen/coursera-dl',
            script=["coursera-dl.py"]
            requires=['argparse', 'beautifulsoup4'],
           )

