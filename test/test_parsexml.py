#!/usr/bin/env python3

import unittest
import sys, os
import glob
from pprint import pprint
import logging as L

# Adding this to sys.path makes the test work if you just run it directly.
from smrtino.ParseXML import get_readset_info

DATA_DIR = os.path.abspath(os.path.dirname(__file__) + '/mock_examples')
VERBOSE = os.environ.get('VERBOSE', '0') != '0'

L.basicConfig(level=(L.DEBUG if VERBOSE else L.WARNING))

class T(unittest.TestCase):

    def test_subreadset(self):
        """ Load an XML file from one of our examples.
        """
        xmlfile = DATA_DIR + "/r54041_20180613_132039/1_A01/subreadset.xml"

        info = get_readset_info( xmlfile )

        self.assertEqual(info, {
                        'cell_id':    'm54041_180613_132945',
                        '_parts':     ['subreads', 'scraps'],
                        'readset_type': 'SubreadSet (CLR)',
                        'run_id':     'r54041_20180613_132039',
                        'run_slot':   '1_A01',
                        'ws_desc':    '',
                        'ws_name':    '10978PJ0005L05_2.5pM',
                        'ws_project': '10978',
                         })

    def test_consensusreadset(self):
        """ Load an XML file from one of our HiFi examples.
        """
        xmlfile = DATA_DIR + "/r64175e_20201211_163702/1_A01/m64175e_201211_164938.consensusreadset.xml"

        info = get_readset_info( xmlfile )

        self.assertEqual(info, {
                        'cell_id':      'm64175e_201211_164938',
                        '_parts':       ['reads'],
                        'readset_type': 'ConsensusReadSet (HiFi)',
                        'run_id':       'r64175e_20201211_163702',
                        'run_slot':     '1_A01',
                        'ws_desc':      '',
                        'ws_name':      '16160CT0001L01',
                        'ws_project':   '16160',
                         })

if __name__ == '__main__':
    unittest.main()

