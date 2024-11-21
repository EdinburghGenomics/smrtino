#!/usr/bin/env python3

"""Test some functions within compile_cell_info.py
"""

import sys, os, re
import unittest
import logging

LIMA_REPORTS = os.path.abspath(os.path.dirname(__file__) + '/lima_reports')
VERBOSE = os.environ.get('VERBOSE', '0') != '0'

from compile_cell_info import load_lima_counts, summarize_lima_counts

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
    def test_lima_counts_empty(self):
        self.assertEqual(load_lima_counts('/dev/null'), {})

    def test_m84140_240919_131445_s1(self):
        """This was a failed cell but a nice test case for barcode reporting.
        """
        expected = { 'Number of samples': 4,
                     'Assigned Reads (%)': "99.59",
                     'CV': "0.93" }

        lima_counts = load_lima_counts(LIMA_REPORTS + "/hifi_reads.lima_counts.txt")

        self.assertEqual(len(lima_counts), 5)
        self.assertEqual(lima_counts['unassigned'], 9)

        lima_summary = summarize_lima_counts(lima_counts)

        self.assertEqual(lima_summary, expected)

if __name__ == '__main__':
    unittest.main()
