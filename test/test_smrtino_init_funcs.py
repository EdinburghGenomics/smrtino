#!/usr/bin/env python3

"""Test some utility functions"""

# Note this will get discovered and run as a test. This is fine.

import sys, os, re
import unittest
import logging

DATA_DIR = os.path.abspath(os.path.dirname(__file__) + '/examples')
VERBOSE = os.environ.get('VERBOSE', '0') != '0'

from smrtino import load_yaml

class T(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        #Prevent the logger from printing messages - I like my tests to look pretty.
        if VERBOSE:
            logging.getLogger().setLevel(logging.DEBUG)
        else:
            logging.getLogger().setLevel(logging.CRITICAL)

    def setUp(self):
        # See the errors in all their glory
        self.maxDiff = None

    ### THE TESTS ###
    def test_load_yaml(self):

        ydata = load_yaml(DATA_DIR + "/m64175e_220401_135226.link.yml")

        self.assertEqual( [k for k in ydata.keys() if k.startswith('cell')],
                          "cell_dir cell_type cell_uuid".split() )

if __name__ == '__main__':
    unittest.main()
