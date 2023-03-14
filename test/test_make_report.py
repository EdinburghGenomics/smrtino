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
from collections import OrderedDict
from unittest.mock import MagicMock, patch, mock_open

DATA_DIR = os.path.abspath(os.path.dirname(__file__) + '/examples')
VERBOSE = os.environ.get('VERBOSE', '0') != '0'

# from lib_or_script import functions
from make_report import ( make_table, format_cell, blockquote, format_report,
                          load_all_inputs, get_qc_link, get_run_metadata,
                          get_pipeline_metadata, load_status_info, rejig_status_info,
                          escape_md )

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


            # About this run

            <dl class="dl-horizontal">
            </dl>

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

            # Fudge is no longer in this function

    def test_rejig_status_info(self):
        """Function that returns a version of status_info good for the report.
        """
        some_info = dict( RunID = 'r54321_20181019_123127',
                          Instrument = '54321',
                          Cells = '1_A01 2_B01 3_C01 4_D01',
                          CellsReady = '1_A01',
                          CellsAborted = '',
                          StartTime = 'Fri Oct 19 13:31:59 2018',
                          PipelineStatus = 'complete',
                          _foo = 'bar' )

        expected1 = OrderedDict([ ( "RunID",           'r54321_20181019_123127' ),
                                  ( "Instrument",      '54321' ),
                                  ( "Cells",           '1_A01 2_B01 3_C01 4_D01' ),
                                  ( "StartTime",       'Fri Oct 19 13:31:59 2018' ),
                                  ( "PipelineStatus",  'complete' ) ])
        rejig1 = rejig_status_info( some_info )
        # Double comparison because the difference between dicts is easier to see in the
        # error message.
        self.assertEqual(dict(rejig1), dict(expected1))
        self.assertEqual(rejig1, expected1)

        expected2 = OrderedDict([ ( "Experiment",      'K123' ),
                                  ( "SMRTLink Run QC", ('label','link') ),
                                  ( "RunID",           'r54321_20181019_123127' ),
                                  ( "Instrument",      'Sequel2e_64175e' ),
                                  ( "Cells",           '1_A01 2_B01 3_C01 4_D01' ),
                                  ( "StartTime",       'Fri Oct 19 13:31:59 2018' ),
                                  ( "PipelineStatus",  'complete' ) ])
        rejig2 = rejig_status_info( some_info,
                                    smrtlink_qc_link = ('label', 'link'),
                                    experiment = 'K123',
                                    instrument = 'Sequel2e_64175e' )
        self.assertEqual(dict(rejig2), dict(expected2))
        self.assertEqual(rejig2, expected2)

    def test_get_qc_link(self):
        """Find the Run QC link from multiple YAMLs
           This also serves as a test of load_all_inputs.
        """
        # When the files are good and the links all match
        examples1 = [ f"{DATA_DIR}/{c}.link.yml" for c in [ "m64175e_220401_135226",
                                                            "m64175e_220402_224908",
                                                            "m64175e_220404_060823" ] ]
        all_yamls1 = load_all_inputs(examples1)

        if VERBOSE:
            pprint(all_yamls1)

        self.assertEqual( get_qc_link(all_yamls1),
                          ('dfb8647e-eb3e-4b6c-9351-92930fb6f058',
                           'https://smrtlink.genepool.private:8243/sl/run-qc/dfb8647e-eb3e-4b6c-9351-92930fb6f058') )

        # Add another bad yml and it should break
        examples2 = examples1 + [ f"{DATA_DIR}/m64175e_220406_123456.link.yml" ]
        all_yamls2 = load_all_inputs(examples2)

        self.assertEqual( get_qc_link(all_yamls2), None )

    def test_get_run_metadata(self):

        # Make an all_yamls structure as if loaded from load_all_inputs()
        r1 = dict( Instrument = 'Rod',
                   Operator = 'Jane',
                   Experiment = 'Freddie' )
        r2 = dict( Instrument = 'Rod',
                   Experiment = 'Bungle' )
        r3 = dict( Instrument = 'Rod',
                   Experiment = 'George' )

        all_yamls = dict(info = dict( i1 = dict( _run = r1 ),
                                      i2 = dict( _run = r2 ),
                                      i3 = dict( _run = r3 ),
                                      i4 = dict( _foo = 'bar' ) ) )

        # Base case
        self.assertEqual( get_run_metadata(dict(inof=dict()), 'Instrument'), None )

        # Normal case
        self.assertEqual( get_run_metadata(all_yamls, 'Instrument'), 'Rod' )

        # Partially missing data case
        self.assertEqual( get_run_metadata(all_yamls, 'Operator'), 'Jane' )

        # Contradictory data case
        self.assertEqual( get_run_metadata(all_yamls, 'Experiment'), 'Bungle, Freddie, George' )


    def test_add_pdf(self):
        """The load_all_inputs() function can now tack on PDFs. It's a bit hacky but
           it allows me to do all the SMRTLink interaction in one Snakefile and not munge
           the info.yaml files.
        """
        inputs1 = [ "foo/bar.pdf" ]

        res1 = load_all_inputs(inputs1)

        self.assertEqual( res1, dict(info={}, link={}, pdf={'bar': "foo/bar.pdf"}) )

    def test_get_qc_link_missing(self):
        """If we couldn't get any links from the API we should still be able to make a report,
           just without the links.
        """
        examples3 = [ f"{DATA_DIR}/m64175e_220406_000000.link.yml" ]
        all_yamls3 = load_all_inputs(examples3)

        # Missing links mean no result
        self.assertEqual( get_qc_link(all_yamls3), None )

        # But partially missing links are OK, I guess
        examples4 = examples3 + [ f"{DATA_DIR}/m64175e_220406_123456.link.yml" ]
        all_yamls4 = load_all_inputs(examples4)
        self.assertEqual( get_qc_link(all_yamls4),
                          ('dfb8647e-eb3e-4b6c-9351-92930fb6f666',
                           'https://smrtlink.genepool.private:8243/sl/run-qc/dfb8647e-eb3e-4b6c-9351-92930fb6f666') )

    def test_escape_md(self):
        # Double backslash is the most confusing.
        self.assertEqual( escape_md(r'\ '), r'\\ ')

        # And all the rest
        self.assertEqual( escape_md(r'<[][\`*_{}()#+-.!>'),
                          r'\<\[\]\[\\\`\*\_\{\}\(\)\#\+\-\.\!\>' )

if __name__ == '__main__':
    unittest.main()
