#!/usr/bin/env python3

"""Test the compile_bc_info.py script with a sample barcode."""

import sys, os, re
import unittest
import logging
import yaml

from unittest.mock import Mock

DATA_DIR = os.path.abspath(os.path.dirname(__file__) + '/compile_bc_info')
VERBOSE = os.environ.get('VERBOSE', '0') != '0'

from compile_bc_info import gen_info

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

    def test_sequel2(self):
        """Test the equivalent of the command:

           $ compile_bc_info.py m64175e_221028_133532.consensusreadset.xml \
                                -s m64175e_221028_133532.*reads.cstats.yaml \
                                -p m64175e_221028_133532.*plots.yaml

           Expected output is m64175e_221028_133532.info.yaml
        """
        ddir = f"{DATA_DIR}/r64175e_20221028_133532"
        cellid = "m64175e_221028_133532"
        args = self.get_mock_args()
        args.xmlfile = [f"{ddir}/{cellid}.consensusreadset.xml"]
        args.stats.extend([ f"{ddir}/{cellid}.reads.cstats.yaml",
                            f"{ddir}/{cellid}.hifi_reads.cstats.yaml" ])
        args.plots.extend([ f"{ddir}/{cellid}.histoplots.yaml",
                            f"{ddir}/{cellid}.blobplots.yaml" ])

        with open(f"{ddir}/{cellid}.info.yaml") as fh:
            expected = yaml.safe_load(fh)

        # Run the actual thing
        info = gen_info(args)

        self.assertEqual(info, expected)

    def test_sequel2_with_runxml(self):
        """Test the equivalent of:

           $ compile_cell_info.py m64175e_221028_133532.consensusreadset.xml \
                                  -r m64175e_221028_133532.run.metadata.xml

           Expected output is m64175e_221028_133532.info2.yaml
        """
        ddir = f"{DATA_DIR}/r64175e_20221028_133532"
        cellid = "m64175e_221028_133532"
        args = self.get_mock_args()
        args.xmlfile = [f"{ddir}/{cellid}.consensusreadset.xml"]
        args.runxml = f"{ddir}/{cellid}.run.metadata.xml"

        with open(f"{ddir}/{cellid}.info2.yaml") as fh:
            expected = yaml.safe_load(fh)

        # Run the actual thing
        info = gen_info(args)

        self.assertEqual(info, expected)

if __name__ == '__main__':
    unittest.main()
