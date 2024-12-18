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
                          format_per_barcode, load_input,
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

    def assertODEqual(self, od1, od2):
        """Tests that two dictionaries have the same content and the same ordering.
        """
        self.assertEqual(dict(od1), dict(od2))
        self.assertEqual(list(od1), list(od2))

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

                         ## Basics

                         <dl class="dl-horizontal">
                         <dt>bs_project</dt>
                         <dd><span style='color: Tomato;'>None</span></dd>
                         </dl>
                      """)

        res = format_cell(dict())
        self.assertEqual("\n".join(res) + "\n", expected)

    def test_format_barcode(self):
        """Another function that makes PanDoc output.
           Again, test with minimal input for now.
        """
        expected = dd("""\

                         # placeholder title \\#

                         <dl class="dl-horizontal">
                         </dl>
                      """)

        res = format_per_barcode(dict(barcode="x"), None, "placeholder title #")
        self.assertEqual("\n".join(res) + "\n", expected)

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
        empty_bc = dict( barcode = "bc1--bc1",
                         barcode_squashed = "bc1",
                         ws_name = "test_ws_name",
                         bs_project = "00000",
                         bs_name = "test_bs_name" )
        empty_rep  = format_report( dict( cell_id = "test_cell_id",
                                          project = "11111",
                                          barcodes = [empty_bc] ),
                                    pipedata = dict(),
                                    run_status = dict(),
                                    rep_time = datetime(2000,11,2) )

        expected_empty = dd("""
            % PacBio SMRT cell test\\_cell\\_id
            % SMRTino version None
            % Thursday, 02 Nov 2000 00:00


            # About the whole run

            [\u2bb0 Reports for all cells](./)

            <dl class="dl-horizontal">
            </dl>

            # SMRT cell info


            ## Basics

            <dl class="dl-horizontal">
            <dt>barcodes</dt>
            <dd>bc1</dd>
            <dt>cell_id</dt>
            <dd>test\\_cell\\_id</dd>
            <dt>project</dt>
            <dd>11111</dd>
            </dl>

            # QC for barcode bc1

            <dl class="dl-horizontal">
            <dt>bs_project</dt>
            <dd>00000</dd>
            <dt>bs_name</dt>
            <dd>test\_bs\_name</dd>
            </dl>

            *~~~*
            """)

        self.assertEqual("\n".join(empty_rep), expected_empty.strip())

        # TODO - try with some real data.

    def test_get_pipeline_metadata(self):
        """This mostly just reads the version log
        """
        with patch("os.environ", dict(SMRTINO_VERSION='1.7.19')):
            pmd = get_pipeline_metadata( DATA_DIR + '/rundir1/pbpipeline' )

        self.assertEqual( pmd,
                          dict( version = "1.7.2+1.7.3+1.7.19",
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

            res = dict(load_status_info("xxx"))

            self.assertODEqual( res, expected )

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

        expected1 = OrderedDict([ ( "Cells",           '4' ),
                                  ( "RunID",           'r54321_20181019_123127' ),
                                  ( "Instrument",      '54321' ),
                                  ( "StartTime",       'Fri Oct 19 13:31:59 2018' ) ])
        rejig1 = rejig_status_info( some_info, {} )
        # Double comparison because the difference between dicts is easier to see in the
        # error message, and then we need to check the ordering too.
        self.assertODEqual(rejig1, expected1)

        expected2 = OrderedDict([ ( "Cells",           '4' ),
                                  ( "Experiment",      'K123' ),
                                  ( "SMRTLink Run QC", ('label','link') ),
                                  ( "RunID",           'r54321_20181019_123127' ),
                                  ( "Instrument",      'Sequel2e_64175e' ),
                                  ( "StartTime",       'Fri Oct 19 13:31:59 2018' ) ])
        rejig2 = rejig_status_info( some_info,
                                    cell_data = dict(
                                        _links = dict(
                                            smrtlink_run_uuid = 'label',
                                            smrtlink_run_link = 'link' ),
                                        _run = dict(
                                            ExperimentId = 'K123',
                                            Instrument = 'Sequel2e_64175e' ) ) )
        self.assertODEqual(rejig2, expected2)

    def test_get_qc_link(self):
        """Find the Run QC link
           This test is kinda pointless since we switched to reporting one
           cell at a time.
           # TODO - have a better test of load_input()
        """
        # When the files are good and the links all match
        example_info = f"{DATA_DIR}/minimal.info.yaml"
        example_link = f"{DATA_DIR}/m64175e_220401_135226.link.yaml"
        loaded_info = load_input(example_info, example_link)

        if VERBOSE:
            pprint(loaded_info)

        self.assertEqual( ( loaded_info['_links']['smrtlink_run_uuid'],
                            loaded_info['_links']['smrtlink_run_link'] ),
                          ('dfb8647e-eb3e-4b6c-9351-92930fb6f058',
                           'https://smrtlink.genepool.private:8243/sl/run-qc/dfb8647e-eb3e-4b6c-9351-92930fb6f058') )

    def test_barcode_list_squash(self):
        """In the "SMRT cell info" section, under "Basics", the list of barcodes should
           be reported in squashed format, and likewise the "QC for barcode ..." headings
           should use the squashed format. But for cell m84140_241213_122201_s4 this
           is not happening. So test it.
        """
        # As a reminder, the file
        # m84140_241213_122201_s4/bcM0001--bcM0001/m84140_241213_122201_s4.info.bcM0001--bcM0001.yaml
        # loaded via m84140_241213_122201_s4.info.yaml contains both the squashed and unsquashed name
        # of the barcode.

        cell_info = f"{DATA_DIR}/r84140_20241213_121411/m84140_241213_122201_s4.info.yaml"

        loaded_data = load_input(cell_info)
        rep = list(format_report(loaded_data))

        # Grep out the barcode summary line
        barcodes_heading = rep.index("<dt>barcodes</dt>")
        self.assertEqual(rep[barcodes_heading+1], r"<dd>bcM0001\, bcM0002\, bcM0003</dd>")

        # And the heading lines
        qc_headings = [ l for l in rep if l.startswith("# QC for") ]
        self.assertEqual(qc_headings, [
                            "# QC for barcode bcM0001",
                            "# QC for barcode bcM0002",
                            "# QC for barcode bcM0003",
                            "# QC for unassigned reads", ])


    def test_escape_md(self):
        # Double backslash is the most confusing.
        self.assertEqual( escape_md(r'\ '), r'\\ ')

        # And all the rest
        self.assertEqual( escape_md(r'<[][\`*_{}()#+-.!,>@foo'),
                          r'\<\[\]\[\\\`\*\_\{\}\(\)\#\+\-\.\!\,\>@foo' )

if __name__ == '__main__':
    unittest.main()
