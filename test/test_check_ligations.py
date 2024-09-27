#!/usr/bin/env python3

"""Test for the check_ligations.py script"""

import sys, os, re
import unittest
import logging

DATA_DIR = os.path.abspath(os.path.dirname(__file__) + '/examples')
VERBOSE = os.environ.get('VERBOSE', '0') != '0'

from check_ligations import make_cutoff

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

    def tearDown(self):
        pass

    ### THE TESTS ###
    def test_make_cutoff(self):
        # Normally, any ligation with >=500 reads will be counted
        self.assertEqual(make_cutoff(1000), 500)

        # If the percentile is set to 90, that means >=900. Ditto 100
        self.assertEqual(make_cutoff(1000, percent=90), 900)
        self.assertEqual(make_cutoff(1000, percent=100), 1000)

        # If the number is 1, we always want to return 1 unless the percent is 0
        self.assertEqual(make_cutoff(1, percent=10), 1)
        self.assertEqual(make_cutoff(1, percent=90), 1)
        self.assertEqual(make_cutoff(1, percent=100), 1)
        self.assertEqual(make_cutoff(1000, percent=0), 0)

if __name__ == '__main__':
    unittest.main()
