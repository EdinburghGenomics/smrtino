#!/usr/bin/env python3

"""Template/boilerplate for writing new test classes"""

# Note this will get discovered and run as a test. This is fine.

import sys, os, re
import unittest
import logging

DATA_DIR = os.path.abspath(os.path.dirname(__file__) + "/blobplot_stats")
VERBOSE = os.environ.get('VERBOSE', '0') != '0'

from blobplot_stats_to_species import load_stat_file, tables_to_verdict

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

    def load_example(self, basename, parts=("species", "order", "phylum")):

        res = []
        for part in parts:
            res.append(load_stat_file(f"{DATA_DIR}/{basename}.reads.{part}.blobplot.stats.txt"))

        return res


    ### THE TESTS ###
    def test_basics(self):

        tables1 = self.load_example("m64175e_220402_224908")

        # With defaults
        verdict1 = tables_to_verdict(tables1, 10.0, 20.0)
        self.assertEqual(verdict1, ["Mus musculus (27.1%)", "Cricetulus griseus (26.7%)"])

        # If the cutoff is set to 30 we should fall back to checking order
        verdict2 = tables_to_verdict(tables1, 30.0, 20.0)
        self.assertEqual(verdict2, ["Rodentia (60.6%)"])

        # If the cutoff is 61 we should fall back to phylum
        verdict3 = tables_to_verdict(tables1, 61.0, 20.0)
        self.assertEqual(verdict3, ["Chordata (61.0%)"])

        # If the cutoff is 61.1 we get nothing
        verdict4 = tables_to_verdict(tables1, 61.1, 20.0)
        self.assertEqual(verdict4, [])

        # And if the dominance was 0.2 we only get mouse
        verdict5 = tables_to_verdict(tables1, 10.0, 0.2)
        self.assertEqual(verdict5, ["Mus musculus (27.1%)"])


if __name__ == '__main__':
    unittest.main()
