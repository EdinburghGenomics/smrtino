#!/usr/bin/env python3

"""Test the compile_bc_info.py script with a sample barcode."""

import sys, os, re
import unittest
import logging
import yaml

from unittest.mock import NonCallableMock
from io import StringIO

DATA_DIR = os.path.abspath(os.path.dirname(__file__) + '/revio_out_examples')
VERBOSE = os.environ.get('VERBOSE', '0') != '0'

from compile_bc_info import gen_info

class NoneMock(NonCallableMock):
    """A Mock where fetching undefined attributes returns None,
       rather then a new Mock object. Useful for mocking command
       line args.
    """
    def _get_child_mock(self, **kw):
        return None

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
        args = NoneMock()

        args.plots = []
        args.stats = []
        args.debug = False

        # For all other attributes, NoneMock returns None

        return args

    def test_revio_nobc(self):
        """Test the equivalent of the command:

           $ compile_bc_info.py m84140_240116_163605_s1.hifi_reads.all.consensusreadset.xml \
                                -s m84140_240116_163605_s1.*reads.foo.cstats.yaml \
                                -p m84140_240116_163605_s1.*plots.yaml

           Expected output is m84140_240116_163605_s1.info.yaml
        """
        ddir = f"{DATA_DIR}/r84140_20240116_162812"
        cellid = "m84140_240116_163605_s1"
        args = self.get_mock_args()
        args.xmlfile = [f"{ddir}/{cellid}.hifi_reads.all.consensusreadset.xml"]
        args.stats.extend([ f"{ddir}/{cellid}.fail_reads.foo.cstats.yaml",
                            f"{ddir}/{cellid}.hifi_reads.foo.cstats.yaml" ])
        args.plots.extend([ f"{ddir}/{cellid}.histoplots.yaml",
                            f"{ddir}/{cellid}.blobplots.yaml" ])

        with open(f"{ddir}/{cellid}.info.yaml") as fh:
            expected = yaml.safe_load(fh)

        # Run the actual thing.

        # Note that _cstats['Barcode'] picks up the value 'foo' from the cstats.yaml
        # filenames, even though info['barode'] is not present.
        info = gen_info(args)

        self.assertEqual(info, expected)

    def test_revio_nobc_with_runxml(self):
        """Test the equivalent of:

           $ compile_cell_info.py m84140_240116_163605_s1.hifi_reads.all.consensusreadset.xml \
                                  -r m84140_240116_163605_s1.metadata.xml

           Expected output is m84140_240116_163605_s1.info2.yaml
        """
        ddir = f"{DATA_DIR}/r84140_20240116_162812"
        cellid = "m84140_240116_163605_s1"
        args = self.get_mock_args()
        args.xmlfile = [f"{ddir}/{cellid}.hifi_reads.all.consensusreadset.xml"]
        args.metaxml = f"{ddir}/{cellid}.metadata.xml"

        with open(f"{ddir}/{cellid}.info2.yaml") as fh:
            expected = yaml.safe_load(fh)

        # Run the actual thing
        info = gen_info(args)

        self.assertEqual(info, expected)

    def test_revio_withbc(self):
        """Test the equivalent of:

           $ compile_cell_info.py m84140_240116_183509_s2.hifi_reads.bc1008.consensusreadset.xml
        """
        ddir = f"{DATA_DIR}/r84140_20240116_162812"
        cellid = "m84140_240116_183509_s2"
        args = self.get_mock_args()
        args.xmlfile = [f"{ddir}/{cellid}.hifi_reads.bc1008.consensusreadset.xml"]

        with open(f"{ddir}/{cellid}.bc1008.info2.yaml") as fh:
            expected = yaml.safe_load(fh)

        # Run the actual thing
        info = gen_info(args)

        self.assertEqual(info, expected)

    def test_taxon_binning(self):
        """Test the equivalent of:

           $ compile_cell_info.py -t <(echo 'taxon name') \
                                  -b <(echo binned) \
                                  m84140_240116_183509_s2.hifi_reads.bc1008.consensusreadset.xml

           Note this test is a superset of test_revio_withbc() so if both are failing debug
           that one first.
        """
        ddir = f"{DATA_DIR}/r84140_20240116_162812"
        cellid = "m84140_240116_183509_s2"
        args = self.get_mock_args()
        args.xmlfile = [f"{ddir}/{cellid}.hifi_reads.bc1008.consensusreadset.xml"]

        with open(f"{ddir}/{cellid}.bc1008.info3.yaml") as fh:
            expected = yaml.safe_load(fh)

        # Supply taxon and binning. To save using actual files we can pass file descriptors
        # that will work with open(). This is a bit shonky and relies on pipe buffers not
        # locking up but is fine for making a test.
        args.taxon, tax_out = os.pipe()
        with open(tax_out, "w") as pfh: print("taxon name", file=pfh)
        args.binning, binning_out = os.pipe()
        with open(binning_out, "w") as pfh: print("binned", file=pfh)

        # Run the actual thing
        info = gen_info(args)

        self.assertEqual(info, expected)

if __name__ == '__main__':
    unittest.main()
