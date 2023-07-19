#!/usr/bin/env python3

"""Test the compile_cell_info.py script with a sample cell."""

import sys, os, re
import unittest
import logging
import yaml

from unittest.mock import Mock

DATA_DIR = os.path.abspath(os.path.dirname(__file__) + '/compile_cell_info')
VERBOSE = os.environ.get('VERBOSE', '0') != '0'

from compile_cell_info import gen_info

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
    def get_mock_args(self):
        args = Mock()

        args.xmlfile = None
        args.runxml = None
        args.plots = []
        args.stats = []
        args.taxon = []
        args.debug = False

        return args

    def test_sample1(self):
        """Test the equivalent of the command:

           $ compile_cell_info.py m64175e_221028_133532.consensusreadset.xml \
                                  -s m64175e_221028_133532.*reads.cstats.yml \
                                  -p m64175e_221028_133532.*plots.yml

           Expected output is m64175e_221028_133532.info.yml
        """
        cellid = "m64175e_221028_133532"
        args = self.get_mock_args()
        args.xmlfile = [f"{DATA_DIR}/{cellid}.consensusreadset.xml"]
        args.stats.extend([ f"{DATA_DIR}/{cellid}.reads.cstats.yml",
                            f"{DATA_DIR}/{cellid}.hifi_reads.cstats.yml" ])
        args.plots.extend([ f"{DATA_DIR}/{cellid}.histoplots.yml",
                            f"{DATA_DIR}/{cellid}.blobplots.yml" ])

        with open(f"{DATA_DIR}/{cellid}.info.yml") as fh:
            expected = yaml.safe_load(fh)

        # Run the actual thing
        info = gen_info(args)

        self.assertEqual(info, expected)

    def test_sample1_with_runxml(self):
        """Test the equivalent of:

           $ compile_cell_info.py m64175e_221028_133532.consensusreadset.xml \
                                  -r m64175e_221028_133532.run.metadata.xml

           Expected output is m64175e_221028_133532.info2.yml
        """
        cellid = "m64175e_221028_133532"
        args = self.get_mock_args()
        args.xmlfile = [f"{DATA_DIR}/{cellid}.consensusreadset.xml"]
        args.runxml = f"{DATA_DIR}/{cellid}.run.metadata.xml"

        with open(f"{DATA_DIR}/{cellid}.info2.yml") as fh:
            expected = yaml.safe_load(fh)

        # Run the actual thing
        info = gen_info(args)

        self.assertEqual(info, expected)

if __name__ == '__main__':
    unittest.main()
