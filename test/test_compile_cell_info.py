#!/usr/bin/env python3

import unittest
import sys, os
import glob
from pprint import pprint
import logging as L

# Adding this to sys.path makes the test work if you just run it directly.
sys.path.insert(0,'.')
from compile_cell_info import get_the_info, ET

DATA_DIR = os.path.abspath(os.path.dirname(__file__) + '/mock_examples')
VERBOSE = os.environ.get('VERBOSE', '0') != '0'

L.basicConfig(level=(L.DEBUG if VERBOSE else L.WARNING))

class T(unittest.TestCase):

    def test_1(self):
        """ Load an XML file from one of our examples.
        """
        xmlfile = DATA_DIR + "/r54041_20180613_132039/1_A01/subreadset.xml"

        info = get_the_info( ET.parse(xmlfile).getroot() )

        self.assertEqual(info, {
                        'cell_id': 'm54041_180613_132945',
                        'run_id': 'r54041_20180613_132039',
                        'run_slot': '1_A01',
                        'ws_desc': '',
                        'ws_name': '10978PJ0005L05_2.5pM',
                        'ws_project': '10978',
                         })

if __name__ == '__main__':
    unittest.main()

