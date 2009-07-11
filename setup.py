import ez_setup
ez_setup.use_setuptools()
from setuptools import setup, find_packages
import sys

install_requires = ['ply']

PACKAGE_NAME = 'rhizome2'
pyver = sys.version_info[:2]
if pyver < (2,4):
    print "Sorry, %s requires version 2.4 or later of Python" % PACKAGE_NAME
    sys.exit(1)        
if pyver < (2,5):
  install_requires.extend(['wsgiref'])
if pyver < (2,6):
  install_requires.extend(['simplejson'])

setup(
    name = PACKAGE_NAME,
    version = "0.0.1",
    packages = ['rx', 'jql'],
    install_requires = install_requires,

   XXXentry_points = {
        'console_scripts': [
            'foo = my_package.some_module:main_func',
            'bar = other_module:some_func',
        ],
    },

)