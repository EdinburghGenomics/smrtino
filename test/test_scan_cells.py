#!/usr/bin/env python3

"""Test the scan_cells script on some Revio runs.

   It can also work on SequelII runs but we're not bothered about these
   any more.
"""

# Note this will get discovered and run as a test. This is fine.

import sys, os, re
import unittest
import logging
import yaml

DATA_DIR = os.path.abspath(os.path.dirname(__file__) + '/revio_examples')
VERBOSE = os.environ.get('VERBOSE', '0') != '0'

from scan_cells import scan_main, parse_args

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

    def get_empty_args(self):
        return parse_args(["--"])

    def scan_revio_run(self, run_name, **kwargs):

        args = self.get_empty_args()
        args.rundir = os.path.join(DATA_DIR, run_name)
        for k, v in kwargs.items():
            setattr(args, k, v)

        return scan_main(args)

    def load_revio_yaml(self, run_name, filename="sc_data.yaml"):
        """Given a run, loads sc_data.yaml
        """
        sc_data = os.path.join(DATA_DIR, run_name, filename)

        with open(sc_data) as yfh:
            return yaml.safe_load(yfh)

    ### THE TESTS ###
    def test_barcoded_run(self):
        r = "r84140_20231018_154254"

        self.assertEqual( self.scan_revio_run(r),
                          self.load_revio_yaml(r) )

        # Also try with the option that sees both cells
        self.assertEqual( self.scan_revio_run(r, xmltrigger=True),
                          self.load_revio_yaml(r, filename="sc_data_all.yaml") )

    def test_smrtlink13_run(self):
        r = "r84140_20240116_162812"

        self.assertEqual( self.scan_revio_run(r),
                          self.load_revio_yaml(r) )

if __name__ == '__main__':
    unittest.main()
