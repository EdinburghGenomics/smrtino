#!/usr/bin/env python3

""" Test for the version of the base counter in the SMRTino pipeline
"""

import sys, os, re
import unittest
import logging
import gzip
from unittest.mock import NonCallableMock, patch
from io import StringIO
from textwrap import dedent as dd

DATA_DIR = os.path.abspath(os.path.dirname(__file__) + '/hifi_examples')
VERBOSE = os.environ.get('VERBOSE', '0') != '0'

from fq_base_counter import main as fq_base_counter_main

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

    def compare_files(self, fh1, fh2):
        self.assertEqual( [ l.rstrip('\n') for l in fh1 ],
                          [ l.rstrip('\n') for l in fh2 ] )

    def test_fq(self):
        """Test that reading the file directly gets the expected result.
        """
        mock_args = NoneMock( infile = [DATA_DIR + '/example_hifi_reads.fastq.gz'] )
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            fq_base_counter_main(mock_args)

        mock_stdout.seek(0)
        with open(DATA_DIR + '/example_hifi_reads.fastq.count') as fh:
            self.compare_files( fh, mock_stdout )


    def test_fh(self):
        """Test that reading from a pipe gets the same result.
        """
        mock_args = NoneMock( infile = ['blah/blah/example_hifi_reads.fastq.gz'], stdin = True )

        with gzip.open(DATA_DIR + '/example_hifi_reads.fastq.gz', 'rb') as fq_fh:
            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                with patch('sys.stdin', NonCallableMock(buffer=fq_fh)) as mock_stdin:
                    fq_base_counter_main(mock_args)

        mock_stdout.seek(0)
        with open(DATA_DIR + '/example_hifi_reads.fastq.count') as fh:
            self.compare_files( fh, mock_stdout )

    def test_empty(self):
        """Test that reading a zer-line file still produces a reasonable result.
        """
        mock_args = NoneMock( infile = ['empty.fastq.gz'], stdin = True )

        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            with patch('sys.stdin', NonCallableMock(buffer=StringIO())) as mock_stdin:
                fq_base_counter_main(mock_args)

        mock_stdout.seek(0)
        result = mock_stdout.read()

        self.assertEqual( result,
                          dd("""\
                                filename:    empty.fastq.gz
                                total_reads: 0
                                read_length: 0
                                total_bases: 0
                                non_n_bases: 0
                             """) )

if __name__ == '__main__':
    unittest.main()
