#!/usr/bin/env python3

import unittest
import sys, os
import glob
from pprint import pprint
import logging as L

DATA_DIR = os.path.abspath(os.path.dirname(__file__) + '/revio_examples')
VERBOSE = os.environ.get('VERBOSE', '0') != '0'

L.basicConfig(level=(L.DEBUG if VERBOSE else L.WARNING))

from smrtino.ParseXML import get_metadata_summary, get_metadata_info, get_readset_info

# The three functions are:
#  get_metadata_summary() - need to read the unmodified metadata files
#  get_metadata_info()    - gets the per-cell info for compile_bc_info.py
#  get_readset_info()     - gets the per-barcode info for compile_bc_info.py

class T(unittest.TestCase):

    revio_meta_xml = [ f"{DATA_DIR}/r84140_20231018_154254/1_C01/metadata/m84140_231018_155043_s3.metadata.xml",
                       f"{DATA_DIR}/r84140_20231018_154254/1_D01/metadata/m84140_231018_162059_s4.metadata.xml",
                       f"{DATA_DIR}/r84140_20231030_134730/1_A01/metadata/m84140_231030_135502_s1.metadata.xml" ]

    smrtlink_13_meta = [ f"{DATA_DIR}/r84140_20240116_162812/m84140_240116_163605_s1.metadata.xml",
                         f"{DATA_DIR}/r84140_20240116_162812/m84140_240116_183509_s2.metadata.xml" ]

    smrtlink_13_rs = [ f"{DATA_DIR}/r84140_20240116_162812/m84140_240116_163605_s1.hifi_reads.all.consensusreadset.xml",
                       f"{DATA_DIR}/r84140_20240116_162812/m84140_240116_183509_s2.hifi_reads.bc1003.consensusreadset.xml",
                       f"{DATA_DIR}/r84140_20240116_162812/m84140_240116_183509_s2.hifi_reads.bc1008.consensusreadset.xml",
                       f"{DATA_DIR}/r84140_20240116_162812/m84140_240116_183509_s2.hifi_reads.unassigned.consensusreadset.xml" ]

    def test_wrong_file(self):
        """All the functions should give a meaningful error if called on the wrong type
           of file.
        """
        with self.assertRaisesRegex(RuntimeError, "must be run on a metadata.xml file"):
            get_metadata_summary(smrtlink_13_rs[0])

        with self.assertRaisesRegex(RuntimeError, "must be run on a metadata.xml file"):
            get_metadata_info(smrtlink_13_rs[0])

        with self.assertRaisesRegex(RuntimeError, "must be run on a readset.xml file"):
            get_readset_summary(smrtlink_13_meta[0])

    def test_meta_summary(self):
        """Try reading a cell metadata file from the Revio to get the
           summary info for the run.
        """
        summ = get_metadata_summary( self.revio_meta_xml[0] )

        self.assertEqual(summ, {
                        'cell_id':       "m84140_231018_155043_s3",
                        'cell_uuid':     "b29fa499-96e9-4973-ae0a-085a75a08f9e",
                        'parts':         ["hifi_reads", "fail_reads"],
                        'readset_type':  "Revio (HiFi)",
                        '_readset_type': "ccsreads",
                        'run_id':        "r84140_20231018_154254",
                        'run_slot':      "1_C01",
                        'ws_desc':       "",
                        'ws_name':       "28850RL0004L02",
                        'ws_project':    "28850",
                        'barcodes':      ["bc1002"],
                         })

    def test_meta_summary_13(self):
        """Try reading a cell metadata file from the Revio to get the
           summary info for the run (with SMRTLink 13)
        """
        summ = get_metadata_summary( self.revio_13_meta[0] )

        self.assertEqual(summ, {
                        'cell_id':       "m84140_240116_183509_s2",
                        'cell_uuid':     "fixme",
                        'parts':         ["hifi_reads", "fail_reads"],
                        'readset_type':  "Revio (HiFi)",
                        '_readset_type': "ccsreads",
                        'run_id':        "r84140_20240116_162812",
                        'run_slot':      "1_B01",
                        'ws_name':       "28850RLpool01",
                        'ws_desc':       "Equal pool of 28850RL0003L01 and 28850RL0006L01",
                        'ws_project':    "28850",
                        'barcodes':      ["bc1003", "bc1008"],
                         })


    def test_meta_info(self):
        """Try reading the cell metadata file to get the cell info
        """
        info = get_metadata_info( self.revio_meta_xml[0] )

        self.assertEqual(info, {
                         'ExperimentId': 'x',
                         'ChipType': 'x',
                         'InstrumentType': 'x',
                         'CreatedBy': 'x',
                         'TimeStampedName': 'x'
                         })

    def test_meta_info_13(self):
        """This cell from SMRTLink 13 actually has 2 barcodes
        """
        info = get_metadata_info( self.smrtlink_13_meta[1] )

        self.assertEqual(info, {
                         'ExperimentId': 'x',
                         'ChipType': 'x',
                         'InstrumentType': 'x',
                         'CreatedBy': 'x',
                         'TimeStampedName': 'x'
                         })

    def test_readset_info_13(self):
        """This will get the info at the barcode level. We have an unbarcoded example,
           a barcoded one, and one from the unassigned reads.
        """
        info_nobc = get_readset_info( self.smrtlink_13_rs[0] )
        self.assertEqual(info_nobc, {})

        info_bc = get_readset_info( self.smrtlink_13_rs[2] )
        self.assertEqual(info_bc, {})

        info_unass = get_readset_info( self.smrtlink_13_rs[3] )
        self.assertEqual(info_unass, {})

    def test_smrtlink_link(self):
        """ I added the ability to generate a link to SMRTLINK
        """
        self.assertEqual( get_readset_info( self.smrtlink_13_rs[0],  smrtlink_base='XXX')['_link'],
                          'XXX/sl/data-management/dataset-detail/f341ca37-cca4-4fd6-9232-50cef558f75f?type=ccsreads' )

        self.assertEqual( get_readset_info( self.smrtlink_13_rs[1],  smrtlink_base='XXX')['_link'],
                          'XXX/sl/data-management/dataset-detail/37220870-92af-4d9b-9ca8-ce4699e0ffbe?type=ccsreads' )

if __name__ == '__main__':
    unittest.main()

