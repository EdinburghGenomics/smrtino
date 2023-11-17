#!/usr/bin/env python3

"""Test the basic functions in smrtino/__init__.py"""

import sys, os, re
import unittest
import logging

from datetime import datetime

DATA_DIR = os.path.abspath(os.path.dirname(__file__) + '/examples')
VERBOSE = os.environ.get('VERBOSE', '0') != '0'

from smrtino import load_yaml, parse_run_name

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

        ydata = load_yaml(DATA_DIR + "/m64175e_220401_135226.link.yaml")

        self.assertEqual( [k for k in ydata.keys() if k.startswith('cell')],
                          "cell_dir cell_type cell_uuid".split() )

    def test_parse_run_name(self):

        r0 = parse_run_name("r_bad")
        self.assertEqual( r0,
                          { 'fullname': 'r_bad',
                            'instrument': 'unknown',
                            'platform': 'unknown',
                            'run_or_cell': '',
                            'rundate': None } )


        # A Sequel I run. What came before Sequel I?
        r1 = parse_run_name("r54041_20190315_135511/")
        self.assertEqual( r1,
                          { 'fullname': 'r54041_20190315_135511',
                            'instrument': '54041',
                            'platform': 'Sequel I',
                            'run_or_cell': 'run',
                            'rundate': datetime(2019, 3, 15, 13, 55, 11) } )

        # A cell on a Sequel II
        r2 = parse_run_name("m64175_201027_161153")
        self.assertEqual( r2,
                          { 'fullname': 'm64175_201027_161153',
                            'instrument': '64175',
                            'platform': 'Sequel II',
                            'run_or_cell': 'cell',
                            'rundate': datetime(2020, 10, 27, 16, 11, 53) } )

        # A run on a Sequel IIe
        r2e = parse_run_name("r64175e_20201027_161153")
        self.assertEqual( r2e,
                          { 'fullname': 'r64175e_20201027_161153',
                            'instrument': '64175e',
                            'platform': 'Sequel IIe',
                            'run_or_cell': 'run',
                            'rundate': datetime(2020, 10, 27, 16, 11, 53) } )
        # Well, until the year 2100...
        self.assertEqual(r2['rundate'], r2e['rundate'])

        # Bad date - too short
        r3 = parse_run_name("r64100e_20027_161153")
        self.assertEqual( r3,
                          { 'fullname': 'r64100e_20027_161153',
                            'instrument': '64100e',
                            'platform': 'Sequel IIe',
                            'run_or_cell': 'run',
                            'rundate': None } )

        # Ra Ra Revio
        r4 = parse_run_name("r84140_20230912_141010")
        self.assertEqual( r4,
                          { 'fullname': 'r84140_20230912_141010',
                            'instrument': '84140',
                            'platform': 'Revio',
                            'run_or_cell': 'run',
                            'rundate': datetime(2023, 9, 12, 14, 10, 10) } )

        # Revio cells have a slot number
        r4m = parse_run_name("m84140_230823_180019_s1")
        self.assertEqual( r4m,
                          { 'fullname': 'm84140_230823_180019_s1',
                            'instrument': '84140',
                            'platform': 'Revio',
                            'run_or_cell': 'cell',
                            'rundate': datetime(2023, 8, 23, 18, 0, 19),
                            'slot' : 's1' } )

        # Correct length but invalid date for some reason
        r5 = parse_run_name("r84140_20230932_251010")
        self.assertEqual( r5,
                          { 'fullname': 'r84140_20230932_251010',
                            'instrument': '84140',
                            'platform': 'Revio',
                            'run_or_cell': 'run',
                            'rundate': None } )

if __name__ == '__main__':
    unittest.main()
