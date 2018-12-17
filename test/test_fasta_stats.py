#!/usr/bin/env python3

"""Test the fasta_stats script is behaving"""

# Note this will get discovered and run as a test. This is fine.

import sys, os, re
import unittest
import logging

DATA_DIR = os.path.abspath(os.path.dirname(__file__) + '/sample_fasta')
VERBOSE = os.environ.get('VERBOSE', '0') != '0'

try:
    sys.path.insert(0, '.')
    from fasta_stats import read_fasta, fasta_to_histo, histo_to_result, fastaline
except:
    #If this fails, you is probably running the tests wrongly
    print("****",
          "To test your working copy of the code you should use the helper script:",
          "  ./run_tests.sh <name_of_test>",
          "or to run all tests, just",
          "  ./run_tests.sh",
          "****",
          sep="\n")
    raise

class T(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        #Prevent the logger from printing messages - I like my tests to look pretty.
        if VERBOSE:
            logging.getLogger().setLevel(logging.DEBUG)
        else:
            logging.getLogger().setLevel(logging.CRITICAL)

    def load_fasta(self, filename):
        with open(os.path.join(DATA_DIR, filename + '.fasta')) as fh:
            return list(read_fasta(fh))

    def load_histo(self, filename):
        with open(os.path.join(DATA_DIR, filename + '.fasta')) as fh:
            return fasta_to_histo(read_fasta(fh))

    ### THE TESTS ###
    def test_empty(self):
        """Test loading the empty file.
        """
        self.assertEqual(self.load_fasta('empty'), [])

        self.assertEqual(self.load_histo('empty'), [])

        self.assertEqual(dict(histo_to_result([], cutoff=0)),
                            { 'Max read length': -1,
                              'Reads' : 0,
                              'Total bases': 0,
                              'N50': -1,
                              '_histo': [] } )

    def test_n50(self):
        """Look at some N50 values for simple files.
        """
        # Single sequence
        self.assertEqual( histo_to_result(self.load_histo('foo1'), cutoff=0)['N50'], 1 )
        self.assertEqual( histo_to_result(self.load_histo('foo1'), cutoff=1)['N50 for reads >=1'], 1 )
        self.assertEqual( histo_to_result(self.load_histo('foo1'), cutoff=2)['N50 for reads >=2'], 1 )

        # Two sequences of length 8 and 9
        self.assertEqual( histo_to_result(self.load_histo('foo2'), cutoff=0)['N50'], 9 )
        self.assertEqual( histo_to_result(self.load_histo('foo2'), cutoff=9)['N50 for reads >=9'], 9 )

        # Three sequences of lengths 5, 5 and 10
        self.assertEqual( histo_to_result(self.load_histo('foo3'), cutoff=0)['N50'], 10 ) # I think??
        self.assertEqual( histo_to_result(self.load_histo('foo3'), cutoff=6)['N50 for reads >=6'], 10 )

        # Or indeed 5, 5, 9 or 5, 5, 11
        self.assertEqual( histo_to_result(self.load_histo('foo4'), cutoff=0)['N50'], 5 )
        self.assertEqual( histo_to_result(self.load_histo('foo4'), cutoff=5)['N50 for reads >=5'], 5 )
        self.assertEqual( histo_to_result(self.load_histo('foo4'), cutoff=6)['N50 for reads >=6'], 9 )
        self.assertEqual( histo_to_result(self.load_histo('foo5'), cutoff=0)['N50'], 11 )

if __name__ == '__main__':
    unittest.main()
