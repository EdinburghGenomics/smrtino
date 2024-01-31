#!/usr/bin/env python3

import unittest
import sys, os
import glob
from pprint import pprint
import logging as L

from smrtino.ParseXML import get_readset_info, get_metadata_info

DATA_DIR = os.path.abspath(os.path.dirname(__file__) + '/mock_examples')
VERBOSE = os.environ.get('VERBOSE', '0') != '0'

L.basicConfig(level=(L.DEBUG if VERBOSE else L.WARNING))

# The three functions are:

# get_metadata_summary() - need to read the unmodified metadata files
# get_metadata_info() - gets the per-cell info for compile_bc_info.py
# get_readset_info() - gets the per-barcode info for compile_bc_info.py

class T(unittest.TestCase):

    xmlfiles = [ f"{DATA_DIR}/r54041_20180613_132039/1_A01/subreadset.xml",
                 f"{DATA_DIR}/r64175e_20201211_163702/1_A01/m64175e_201211_164938.consensusreadset.xml" ]

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

    # This fails firstly because the code is hard-coded now to assume Revio syntax and
    # should probably be removed.
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

