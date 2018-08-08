#!/usr/bin/env python3
# vim: set fileencoding=utf-8 :
import sys, os, re
import unittest
from unittest.mock import patch
from glob import glob
from io import StringIO

from snakemake.workflow import Workflow

class T(unittest.TestCase):
    """ Load all the snakefiles just to check I haven't let in some silly syntax error.
    """
    def setUp(self):
        os.environ['TOOLBOX'] = '/'

    @patch('sys.stdout', new_callable=StringIO)
    def syntax_check(self, sf, mock_stdout):
        """ Check that I can load a given workflow OK
        """
        wf = Workflow(sf, overwrite_config=dict( noyaml=True,
                                                 workdir='.',
                                                 rundir = '.',
                                                 ignore_missing=True))
        wf.include(sf)

        self.assertTrue(len(wf.rules) > 1)

# This bit copied from test_base_mask_extractor in Illuminatus...
# Now add the tests dynamically
for snakefile in glob(os.path.join(os.path.dirname(__file__), '..', 'Snakefile.*')):

    # Note the slightly contorted double-lambda syntax to make the closure.
    sfname = os.path.basename(snakefile).split('.')[1]

    #if any (re.match(b+'$', sfname) for b in BLACKLIST):
    #    continue

    setattr(T, 'test_sf_' + sfname, (lambda d: lambda self: self.syntax_check(d))(snakefile))


if __name__ == '__main__':
    unittest.main()
