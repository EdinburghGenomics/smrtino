#!/usr/bin/env python3

"""Test the script that generates text summaries to send to RT"""

import sys, os, re
import unittest
import logging

DATA_DIR = os.path.abspath(os.path.dirname(__file__) + '/make_summary')
VERBOSE = os.environ.get('VERBOSE', '0') != '0'

from make_summary import load_replinks

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
    def test_load_replinks(self):

        rl1 = load_replinks(f"{DATA_DIR}/report_upload_url.1.txt")

        self.assertEqual(rl1, {
                '1_A01': 'https://smrtino.test/r64175e_20221214_163012/1_A01-m64175e_221214_164117.html',
                '2_B01': 'https://smrtino.test/r64175e_20221214_163012/2_B01-m64175e_221216_033721.html',
                '3_C01': 'https://smrtino.test/r64175e_20221214_163012/3_C01-m64175e_221217_143444.html',
                })

if __name__ == '__main__':
    unittest.main()
