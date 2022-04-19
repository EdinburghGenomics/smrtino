#!/usr/bin/env python3

"""Tests for the script that compiles a Markdown report for the run.
"""

import sys, os, re
import unittest
import logging
import types
from pprint import pprint
from datetime import datetime
from textwrap import dedent as dd
from unittest.mock import MagicMock, patch, mock_open

DATA_DIR = os.path.abspath(os.path.dirname(__file__) + '/examples')
VERBOSE = os.environ.get('VERBOSE', '0') != '0'

# from lib_or_script import functions
from make_report import ( make_table, format_cell, blockquote, format_report,
                          load_all_yamls, get_qc_link,
                          get_pipeline_metadata, load_status_info, escape_md )

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

    # In general, we'll do one test per function

    def test_make_table(self):
        """This should escape everythinng, and generally layout the table properly
        """
        some_data = [ {"_headings": "foo bar b#z".split(),
                       "foo": "hello",
                       "bar": 666,
                       "b#z": 6.666666},
                      {"_headings": [],
                       "foo": "[goodbye]",
                       "bar": -666,
                       "b#z": -6.666666} ]

        expected = dd(r"""
                          |foo|bar|b\#z|
                          |---|---|----|
                          |hello|666|6\.67|
                          |\[goodbye\]|\-666|\-6\.67|
                       """.lstrip("\n"))

        res = make_table(some_data)
        self.assertEqual("\n".join(res), expected)

    def test_format_cell(self):
        """Another function that makes PanDoc output.
           Again, test with minimal input for now.
        """
        expected = dd("""\
                         :::::: {.bs-callout}
                         <dl class="dl-horizontal">
                         <dt>ws_project</dt>
                         <dd><span style='color: Tomato;'>None</span></dd>
                         </dl>
                         ::::::
                      """)

        res = format_cell(dict())
        self.assertEqual("\n".join(res), expected)


    def test_blockquote(self):
        expected = dd("""\
                         > foo
                         > bar baz
                      """)

        res = blockquote("foo\nbar baz")
        self.assertEqual("\n".join(res), "\n" + expected)

    def test_format_report(self):
        """This is a complex function but we'll at least check that the base case works.
        """
        empty_rep  = format_report( dict(info={}, link={}),
                                    pipedata = dict(),
                                    run_status = dict(),
                                    aborted_list = list(),
                                    rep_time = datetime(2000,11,2) )

        expected_empty = dd("""
            % PacBio run None
            % SMRTino version None
            % Thursday, 02 Nov 2000 00:00

            **No SMRT Cells have been processed for this run yet.**

            *~~~*
            """)

        self.assertEqual("\n".join(empty_rep), expected_empty.strip())

        # TODO - try with some real data.

    def test_get_pipeline_metadata(self):
        """This mostly just reads the version log
        """
        with patch("os.environ", dict(SMRTINO_VERSION='99.99')):
            pmd = get_pipeline_metadata( DATA_DIR + '/rundir1/pbpipeline' )

        self.assertEqual( pmd,
                          dict( version = "1.7.2+1.7.3+99.99",
                                rundir = 'rundir1') )


    def test_load_status_info(self):
        some_info = dd("""\
                          RunID: r54321_20181019_123127
                          Instrument: Sequel_54321
                          Cells: 1_A01 2_B01 3_C01 4_D01
                          CellsReady: 1_A01
                          CellsAborted: 4_D01
                          StartTime: Fri Oct 19 13:31:59 2018
                          PipelineStatus: complete
                       """)
        expected = dict( RunID = 'r54321_20181019_123127',
                         Instrument = 'Sequel_54321',
                         Cells = '1_A01 2_B01 3_C01 4_D01',
                         CellsReady = '1_A01',
                         CellsAborted = '4_D01',
                         StartTime = 'Fri Oct 19 13:31:59 2018',
                         PipelineStatus = 'complete' )

        with patch("builtins.open", mock_open(read_data=some_info)) as mf:
            # Unfortunately mock_open doesn't yield a valid iterator until Py3.8, but
            # I think we can fudge it for Py3.6.
            # See https://stackoverflow.com/questions/24779893/customizing-unittest-mock-mock-open-for-iteration
            mf.return_value.__iter__ = lambda self: self
            mf.return_value.__next__ = lambda self: next(iter(self.readline, ''))

            self.assertEqual( dict(load_status_info("xxx")), expected )

            expected['PipelineStatus'] = 'imterminably_waiting'
            self.assertEqual( dict(load_status_info("xxx", fudge='imterminably_waiting')),
                              expected )

    def test_get_qc_link(self):
        """Find the Run QC link from multiple YAMLs
           This also serves as a test of load_all_yamls.
        """
        # When the files are good and the links all match
        examples1 = [ f"{DATA_DIR}/{c}.link.yml" for c in [ "m64175e_220401_135226",
                                                            "m64175e_220402_224908",
                                                            "m64175e_220404_060823" ] ]
        all_yamls1 = load_all_yamls(examples1)

        if VERBOSE:
            pprint(all_yamls1)

        self.assertEqual( get_qc_link(all_yamls1),
                          ('dfb8647e-eb3e-4b6c-9351-92930fb6f058',
                           'https://smrtlink.genepool.private:8243/sl/run-qc/dfb8647e-eb3e-4b6c-9351-92930fb6f058') )

        # Add another bad yml and it should break
        examples2 = examples1 + [ f"{DATA_DIR}/m64175e_220406_123456.link.yml" ]
        all_yamls2 = load_all_yamls(examples2)

        self.assertEqual( get_qc_link(all_yamls2), None )

    def test_escape_md(self):
        # Double backslash is the most confusing.
        self.assertEqual( escape_md(r'\ '), r'\\ ')

        self.assertEqual( escape_md(r'[][\`*_{}()#+-.!'),
                          r'\[\]\[\\\`\*\_\{\}\(\)\#\+\-\.\!' )

if __name__ == '__main__':
    unittest.main()
