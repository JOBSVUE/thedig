#!/usr/bin/env python

from setuptools import setup

setup(name='Transmutation',
      version='0.1.dev0',
      description='Transmutation API : enrich personal data using OSINT techniques',
      author='Badreddine Lejmi',
      author_email='badreddine@ankaboot.fr',
      url='https://github.com/ankaboot-source/transmutation',
      license="AGPL",
      long_description=open("../README.md").read(),
      long_description_content_type='text/markdown',
      install_requires=[l.split(">=")[0] for l in open("requirements.txt")]
     )