#!/usr/bin/env python3

import unittest
import sys, os
import glob
from pprint import pprint
import logging as L

from smrtino.ParseXML import get_readset_info, get_metadata_info

DATA_DIR = os.path.abspath(os.path.dirname(__file__) + '/mock_examples')
DATA_REVIO = os.path.abspath(os.path.dirname(__file__) + '/revio_examples')
VERBOSE = os.environ.get('VERBOSE', '0') != '0'

L.basicConfig(level=(L.DEBUG if VERBOSE else L.WARNING))

class T(unittest.TestCase):

    xmlfiles = [ f"{DATA_DIR}/r54041_20180613_132039/1_A01/subreadset.xml",
                 f"{DATA_DIR}/r64175e_20201211_163702/1_A01/m64175e_201211_164938.consensusreadset.xml" ]

    revio_meta_xml = [ f"{DATA_REVIO}/r84140_20231018_154254/1_C01/metadata/m84140_231018_155043_s3.metadata.xml",
                       f"{DATA_REVIO}/r84140_20231018_154254/1_D01/metadata/m84140_231018_162059_s4.metadata.xml",
                       f"{DATA_REVIO}/r84140_20231030_134730/1_A01/metadata/m84140_231030_135502_s1.metadata.xml" ]

    def test_revio_meta(self):
        """Try reading the new XML format from the Revio
        """
        info = get_metadata_info( self.revio_meta_xml[0] )

        self.assertEqual(info, {
                        'cell_id':       "m84140_231018_155043_s3",
                        'cell_uuid':     "b29fa499-96e9-4973-ae0a-085a75a08f9e",
                        '_parts':        ["reads"],
                        'readset_type':  "Revio (HiFi)",
                        '_readset_type': "ccsreads",
                        'run_id':        "r84140_20231018_154254",
                        'run_slot':      "1_C01",
                        'ws_desc':       "",
                        'ws_name':       "28850RL0004L02",
                        'ws_project':    "28850",
                        'barcodes':      ["bc1002--bc1002"],
                         })

    def test_subreadset(self):
        """ Load an XML file from one of our examples.
        """
        info = get_readset_info( self.xmlfiles[0] )

        self.assertEqual(info, {
                        'cell_id':       'm54041_180613_132945',
                        'cell_uuid':     'f341ca37-cca4-4fd6-9232-50cef558f75f',
                        '_parts':        ['subreads', 'scraps'],
                        'readset_type':  'SubreadSet (CLR)',
                        '_readset_type': 'subreads',
                        'run_id':        'r54041_20180613_132039',
                        'run_slot':      '1_A01',
                        'ws_desc':       '',
                        'ws_name':       '10978PJ0005L05_2.5pM',
                        'ws_project':    '10978',
                         })

    def test_consensusreadset(self):
        """ Load an XML file from one of our HiFi examples.
        """
        info = get_readset_info( self.xmlfiles[1] )

        self.assertEqual(info, {
                        'cell_id':       'm64175e_201211_164938',
                        'cell_uuid':     '37220870-92af-4d9b-9ca8-ce4699e0ffbe',
                        '_parts':        ['reads'],
                        'readset_type':  'ConsensusReadSet (HiFi)',
                        '_readset_type': 'ccsreads',
                        'run_id':        'r64175e_20201211_163702',
                        'run_slot':      '1_A01',
                        'ws_desc':       '',
                        'ws_name':       '16160CT0001L01',
                        'ws_project':    '16160',
                         })

    def test_smrtlink_link(self):
        """ I added the ability to generate a link to SMRTLINK
        """
        self.assertEqual( get_readset_info( self.xmlfiles[0],  smrtlink_base='XXX')['_link'],
                          'XXX/sl/data-management/dataset-detail/f341ca37-cca4-4fd6-9232-50cef558f75f?type=subreads' )

        self.assertEqual( get_readset_info( self.xmlfiles[1],  smrtlink_base='XXX')['_link'],
                          'XXX/sl/data-management/dataset-detail/37220870-92af-4d9b-9ca8-ce4699e0ffbe?type=ccsreads' )

if __name__ == '__main__':
    unittest.main()

