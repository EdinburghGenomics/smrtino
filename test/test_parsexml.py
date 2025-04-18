#!/usr/bin/env python3

import unittest
import sys, os
import glob
from pprint import pprint
import logging as L

DATA_DIR = os.path.abspath(os.path.dirname(__file__) + '/revio_examples')
DATA_DIR_OUT = os.path.abspath(os.path.dirname(__file__) + '/revio_out_examples')
VERBOSE = os.environ.get('VERBOSE', '0') != '0'

L.basicConfig(level=(L.DEBUG if VERBOSE else L.ERROR))

from smrtino.ParseXML import ( get_metadata_summary, get_metadata_info, get_metadata_info2,
                               get_sts_info, get_readset_info,
                               _get_automation_parameters, _get_cellpac, _load_xml )

# The three functions are:
#  get_metadata_summary() - need to read the unmodified metadata files
#  get_metadata_info()    - gets the per-cell info for compile_bc_info.py
#  get_readset_info()     - gets the per-barcode info for compile_bc_info.py

revio_meta_xml = [ f"{DATA_DIR}/r84140_20231018_154254/1_C01/metadata/m84140_231018_155043_s3.metadata.xml",
                   f"{DATA_DIR}/r84140_20231018_154254/1_D01/metadata/m84140_231018_162059_s4.metadata.xml",
                   f"{DATA_DIR}/r84140_20231030_134730/1_A01/metadata/m84140_231030_135502_s1.metadata.xml",
                   f"{DATA_DIR}/r84140_20241007_154722/1_D01/metadata/m84140_241007_155450_s3.metadata.xml" ]

revio_sts_xml = [ f"{DATA_DIR}/r84140_20250121_143858/1_A01/metadata/m84140_250121_144700_s1.sts.xml", ]

revio_meta_xml_2025 = [ f"{DATA_DIR}/r84140_20250121_143858/1_C01/metadata/m84140_250121_185015_s3.metadata.xml", ]

smrtlink_13_meta = [ f"{DATA_DIR_OUT}/r84140_20240116_162812/m84140_240116_163605_s1.metadata.xml",
                     f"{DATA_DIR_OUT}/r84140_20240116_162812/m84140_240116_183509_s2.metadata.xml" ]

smrtlink_13_rs = [ f"{DATA_DIR_OUT}/r84140_20240116_162812/m84140_240116_163605_s1.hifi_reads.all.consensusreadset.xml",
                   f"{DATA_DIR_OUT}/r84140_20240116_162812/m84140_240116_183509_s2.hifi_reads.bc1003.consensusreadset.xml",
                   f"{DATA_DIR_OUT}/r84140_20240116_162812/m84140_240116_183509_s2.hifi_reads.bc1008.consensusreadset.xml",
                   f"{DATA_DIR_OUT}/r84140_20240116_162812/m84140_240116_183509_s2.hifi_reads.unassigned.consensusreadset.xml" ]

class T(unittest.TestCase):

    def setUp(self):
        # See the errors in all their glory
        self.maxDiff = None

    def test_wrong_file(self):
        """All the functions should give a meaningful error if called on the wrong type
           of file.
        """
        with self.assertRaisesRegex(RuntimeError, "must be run on a metadata.xml file"):
            get_metadata_summary(smrtlink_13_rs[0])

        with self.assertRaisesRegex(RuntimeError, "must be run on a metadata.xml file"):
            get_metadata_info(smrtlink_13_rs[0])

        with self.assertRaisesRegex(RuntimeError, "must be run on a readset.xml file"):
            get_readset_info(smrtlink_13_meta[0])

    def test_meta_summary(self):
        """Try reading a cell metadata file from the Revio to get the
           summary info for the run.
        """
        summ = get_metadata_summary( revio_meta_xml[0] )

        self.assertEqual(summ, {
                        'cell_id':       "m84140_231018_155043_s3",
                        'cell_uuid':     "577ccdb1-d463-42b3-bdd9-6fffbf659105",
                        '_parts':        ["hifi_reads", "fail_reads"],
                        'readset_type':  "Revio (HiFi)",
                        '_readset_type': "ccsreads",
                        'run_id':        "r84140_20231018_154254",
                        'run_slot':      "1_C01",
                        'ws_desc':       "",
                        'ws_name':       "28850RL0004L02",
                        'ws_project':    "28850",
                        'barcodes':      ["bc1002"],
                         })

    def test_get_automation_parameters(self):
        """Test the logic that parses all the AutomationParameter elements
           in a cell metadata.xml
           Note that these come from two namespaces, but the names are all unique
           so we just merge them.
        """
        root = _load_xml(revio_meta_xml[0])

        aps = _get_automation_parameters(root)

        self.assertEqual(len(aps), 32)

    def test_get_cellpac(self):
        """Test we can get the CellPac element attribs
        """
        root = _load_xml(revio_meta_xml[0])

        cellpac = _get_cellpac(root)

        self.assertEqual(len(cellpac), 9)

    def test_get_metadata_info2(self):
        """Test the metadata extractor that gets use the info Javier wants for
           his spreadsheet
        """
        md0 = get_metadata_info2(revio_meta_xml[0])
        self.assertEqual(md0, {'adaptive_loading': False,
                               'application': 'hifiReads',
                               'cell_id': 'm84140_231018_155043_s3',
                               'cell_uuid': '577ccdb1-d463-42b3-bdd9-6fffbf659105',
                               'insert_size': 0,
                               'instrument_id': '84140',
                               'instrument_name': 'Obelix',
                               'movie_time': 24,
                               'on_plate_loading_conc': 200,
                               'run_id': 'r84140_20231018_154254',
                               'run_slot': '1_C01',
                               'run_start': '2023-10-18',
                               'smrt_cell_label_number': 'EA046426',
                               'smrt_cell_lot_number': '1000001262',
                               'smrtlink_user': 'cnewman',
                               'version_ics': '12.0.4.197734',
                               'version_chemistry': '12.0.0.172289',
                               'version_smrtlink': '12.0.0.177059',
                               'ws_desc': '',
                               'ws_name': '28850RL0004L02'})

        # Let's add a test for a Kinnex run. Maybe r84140_20241007_154722
        md3 = get_metadata_info2(revio_meta_xml[3])
        self.assertEqual(md3, {'adaptive_loading': True,
                               'application': 'masSeq16SrRNA',
                               'cell_id': 'm84140_241007_155450_s3',
                               'cell_uuid': 'ee1c0ae0-c693-44c1-9767-ab5db6906aca',
                               'insert_size': 18700,
                               'instrument_id': '84140',
                               'instrument_name': 'Obelix',
                               'movie_time': 30,
                               'on_plate_loading_conc': 190,
                               'run_id': 'r84140_20241007_154722',
                               'run_slot': '1_D01',
                               'run_start': '2024-10-07',
                               'smrt_cell_label_number': 'EA133137',
                               'smrt_cell_lot_number': '1000002838',
                               'smrtlink_user': 'hritch',
                               'version_ics': '13.1.0.221972',
                               'version_chemistry': '13.1.0.217683',
                               'version_smrtlink': '13.1.0.221970',
                               'ws_desc': '',
                               'ws_name': '33950NSpool01L01'})

    def test_get_metadata_info2_2025(self):
        """As above, but PacBio changed the file format
        """
        md0 = get_metadata_info2(revio_meta_xml_2025[0])
        self.assertEqual(md0, {'adaptive_loading': True,
                               'application': 'masSeqForIsoSeq',
                               'cell_id': 'm84140_250121_185015_s3',
                               'cell_uuid': '79c79af3-fcd8-4250-b40c-003a80ed7530',
                               'insert_size': 10000,
                               'instrument_id': '84140',
                               'instrument_name': 'Obelix',
                               'movie_time': 30,
                               'on_plate_loading_conc': 185,
                               'run_id': 'r84140_20250121_143858',
                               'run_slot': '1_C01',
                               'run_start': '2025-01-21',
                               'smrt_cell_label_number': 'EA156579',
                               'smrt_cell_lot_number': '1000003526',
                               'smrtlink_user': 'rfoster2',
                               'version_chemistry': '13.3.0.249246',
                               'version_ics': '13.3.0.253824',
                               'version_smrtlink': '25.1.0.257715',
                               'ws_desc': '',
                               'ws_name': '33461BMpool01'})

    def test_meta_summary_13(self):
        """Try reading a cell metadata file from the Revio to get the
           summary info for the run (with SMRTLink 13)
        """
        # With barcodes
        summ0 = get_metadata_summary( smrtlink_13_meta[0] )
        self.assertEqual(summ0, {
                        'cell_id':       "m84140_240116_163605_s1",
                        'cell_uuid':     "5903c172-50e7-48b8-a70b-d0e33ff8e3ff",
                        '_parts':        ["hifi_reads", "fail_reads"],
                        'readset_type':  "Revio (HiFi)",
                        '_readset_type': "ccsreads",
                        'run_id':        "r84140_20240116_162812",
                        'run_slot':      "1_A01",
                        'ws_name':       "28350AA0001L03",
                        'ws_desc':       "",
                        'ws_project':    "28350",
                         })

        # With no barcodes
        summ0 = get_metadata_summary( smrtlink_13_meta[1] )
        self.assertEqual(summ0, {
                        'cell_id':       "m84140_240116_183509_s2",
                        'cell_uuid':     "bee1763c-4332-4a14-91c7-65dbbef2f28c",
                        '_parts':        ["hifi_reads", "fail_reads"],
                        'readset_type':  "Revio (HiFi)",
                        '_readset_type': "ccsreads",
                        'run_id':        "r84140_20240116_162812",
                        'run_slot':      "1_B01",
                        'ws_name':       "28850RLpool01",
                        'ws_desc':       "Equal pool of 28850RL0003L01 and 28850RL0006L01",
                        'ws_project':    "28850",
                        'barcodes':      ["bc1003", "bc1008"],
                         })

    def test_sts_info(self):

        info = get_sts_info( revio_sts_xml[0] )

        # The floats will be rounded a little so test like this
        expected = { 'adapter_dimers': 1.19209e-05, # (as a percentage)
                     'short_inserts': 1.93119e-03,  # (as a percentage)
                     'local_base_rate_median': 2.18531
                   }

        # Check the keys
        self.assertCountEqual(info, expected)

        for k in expected:
            self.assertAlmostEqual(info[k], expected[k])

    def test_meta_info(self):
        """Try reading the cell metadata file to get the cell info
        """
        info = get_metadata_info( revio_meta_xml[0] )

        self.assertEqual(info, {
                         'ExperimentId': '',
                         'ChipType': '25mChip',
                         'InstrumentType': 'Revio',
                         'CreatedBy': 'cnewman',
                         'TimeStampedName': 'r84140_20231018_154254'
                         })

    def test_meta_info_13(self):
        """This cell from SMRTLink 13 actually has 2 barcodes
        """
        info = get_metadata_info( smrtlink_13_meta[1] )

        self.assertEqual(info, {
                         'ExperimentId': 'K0000_id',
                         'ChipType': '25mChip',
                         'InstrumentType': 'Revio',
                         'CreatedBy': 'rfoster2',
                         'TimeStampedName': 'r84140_20240116_162812'
                         })

    def test_readset_info_13(self):
        """This will get the info at the barcode level. We have an unbarcoded example,
           a barcoded one, and one from the unassigned reads.
        """
        info_nobc = get_readset_info( smrtlink_13_rs[0] )
        self.assertEqual(info_nobc, { '_parts': ['hifi_reads', 'fail_reads'],
                                      '_readset_type': 'ccsreads',
                                      'bs_desc': '',
                                      'bs_name': '28350AA0001L03',
                                      'bs_project': '28350',
                                      'cell_id': 'm84140_240116_163605_s1',
                                      'cell_uuid': '5903c172-50e7-48b8-a70b-d0e33ff8e3ff',
                                      'project': '28350',
                                      'readset_type': 'Revio (HiFi)',
                                      'run_id': 'r84140_20240116_162812',
                                      'run_slot': '1_A01',
                                      'ws_desc': '',
                                      'ws_name': '28350AA0001L03',
                                      'ws_project': '28350' })

        info_bc = get_readset_info( smrtlink_13_rs[2] )
        self.assertEqual(info_bc, { '_parts': ['hifi_reads', 'fail_reads'],
                                    '_readset_type': 'ccsreads',
                                    'barcode': 'bc1008',
                                    'barcode_squashed': 'bc1008',
                                    'bs_desc': '',
                                    'bs_name': '28850RL0006L01',
                                    'bs_project': '28850',
                                    'cell_id': 'm84140_240116_183509_s2',
                                    'cell_uuid': 'bee1763c-4332-4a14-91c7-65dbbef2f28c',
                                    'project': '28850',
                                    'readset_type': 'Revio (HiFi)',
                                    'run_id': 'r84140_20240116_162812',
                                    'run_slot': '1_B01',
                                    'ws_desc': 'Equal pool of 28850RL0003L01 and 28850RL0006L01',
                                    'ws_name': '28850RLpool01',
                                    'ws_project': '28850' })

        info_unass = get_readset_info( smrtlink_13_rs[3] )
        self.assertEqual(info_unass, { '_parts': ['hifi_reads', 'fail_reads'],
                                       '_readset_type': 'ccsreads',
                                       'bs_desc': 'Unassigned reads',
                                       'bs_name': 'unassigned',
                                       'cell_id': 'm84140_240116_183509_s2',
                                       'cell_uuid': 'bee1763c-4332-4a14-91c7-65dbbef2f28c',
                                       'project': '28850',
                                       'readset_type': 'Revio (HiFi)',
                                       'run_id': 'r84140_20240116_162812',
                                       'run_slot': '1_B01',
                                       'ws_desc': 'Equal pool of 28850RL0003L01 and 28850RL0006L01',
                                       'ws_name': '28850RLpool01',
                                       'ws_project': '28850' })

    def test_smrtlink_link(self):
        """ I added the ability to generate a link to SMRTLINK
        """
        self.assertEqual( get_readset_info( smrtlink_13_rs[0],  smrtlink_base='XXX')['_link'],
                          'XXX/sl/data-management/dataset-detail/5903c172-50e7-48b8-a70b-d0e33ff8e3ff?type=ccsreads' )

        self.assertEqual( get_readset_info( smrtlink_13_rs[1],  smrtlink_base='XXX')['_link'],
                          'XXX/sl/data-management/dataset-detail/cd81e8fd-86f7-4b24-9a9e-24b2af3413d1?type=ccsreads' )

if __name__ == '__main__':
    unittest.main()

