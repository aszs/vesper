#:copyright: Copyright 2009-2010 by the Vesper team, see AUTHORS.
#:license: Dual licenced under the GPL or Apache2 licences, see LICENSE.
import doctest
import unittest
import glob
from vesper import query, pjson, multipartjson
from vesper.query import engine
import vesper.utils

suite = unittest.TestSuite()
for mod in (query, engine, pjson, multipartjson, vesper.utils):
    suite.addTest(doctest.DocTestSuite(mod))

#for path in glob.glob('../doc/source/*.rst'):
#    suite.addTest(doctest.DocFileSuite(path))

runner = unittest.TextTestRunner()

if __name__ == '__main__':
    runner.run(suite)
