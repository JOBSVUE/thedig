#!/usr/bin/env python

from distutils.core import setup

setup(name='Transmutation',
      version='0.1dev',
      description='Transmutation API : enrich personal data using OSINT techniques',
      author='Badreddine Lejmi',
      author_email='badreddine@ankaboot.fr',
      url='https://github.com/ankaboot-source/transmutation',
      packages=['transmutation', 'transmutation.miners', 'transmutation.api'],
      license="AGPL",
      long_description=open("README.md").read(),
      long_description_content_type='text/markdown'
      install_requires=[l.split(">=")[0] for l in open("requirements.txt")]
     )