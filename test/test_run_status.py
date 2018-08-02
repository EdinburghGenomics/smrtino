#!/usr/bin/env python3

import unittest
import sys, os
import glob
from tempfile import mkdtemp
from shutil import rmtree, copytree
from pprint import pprint

# Adding this to sys.path makes the test work if you just run it directly.
sys.path.insert(0,'.')
from pb_run_status import RunStatus

DATA_DIR = os.path.abspath(os.path.dirname(__file__) + '/status_check_examples')
VERBOSE = os.environ.get('VERBOSE', '0') != '0'

class T(unittest.TestCase):

    #Helper functions:
    def use_run(self, run_id, copy=False, make_run_info=True):
        """Inspect a run.
           If copy=True, copies the selected run into a temporary folder first.
           Sets self.current_run to the run id and
           self.run_dir to the run dir, temporary or otherwise.
           Also returns a RunStatus object for you.
        """
        self.cleanup_run()

        if copy:
            #Make a temp dir
            self.run_dir = self.tmp_dir = mkdtemp()

            #Clone the run folder into it
            copytree( os.path.join(DATA_DIR, run_id),
                      os.path.join(self.run_dir, run_id),
                      symlinks=True )
        else:
            self.run_dir = DATA_DIR

        #Set the current_run variable
        self.current_run = run_id

        #Presumably we want to inspect the new run, so do that too.
        #If you want to change files around, do that then make a new RunStatus
        #by copying the line below.
        if make_run_info:
            return RunStatus(os.path.join(self.run_dir, self.current_run))

    def cleanup_run(self):
        """If self.tmp_dir has been set, delete the temporary
           folder. Either way, clear the currently set run.
        """
        if vars(self).get('tmp_dir'):
            rmtree(self.tmp_dir)

        self.run_dir = self.tmp_dir = None
        self.current_run = None

    def tearDown(self):
        """Avoid leaving temp files around.
        """
        self.cleanup_run()

    def md(self, fp):
        os.makedirs(os.path.join(self.run_dir, self.current_run, fp))

    def touch(self, fp, content="meh"):
        with open(os.path.join(self.run_dir, self.current_run, fp), 'w') as fh:
            print(content, file=fh)

    def rm(self, dp):
        # Careful with this one, it's basically rm -rf
        try:
            rmtree(os.path.join(self.run_dir, self.current_run, dp))
        except NotADirectoryError:
            os.remove(os.path.join(self.run_dir, self.current_run, dp))
    # And the tests...

    def test_run_new( self ):
        """ A totally new run.
        """
        run_info = self.use_run('r54041_20180518_131155')

        self.assertEqual( run_info.get_status(), 'new' )

        # I should get the same via YAML
        self.assertEqual( dictify(run_info.get_yaml())['PipelineStatus:'], 'new' )

        # This run has 7 cells
        self.assertCountEqual( run_info.get_cells(), "1_B01  2_C01  3_D01  4_E01  5_F01  6_G01  7_H01".split() )

    def test_various_states( self ):
        """ Simulate some pipeline activity on that run.
        """
        run_info = self.use_run('r54041_20180518_131155', copy=True)
        self.md('pbpipeline')

        def gs():
            """ Clear the cache and re-read the status
            """
            run_info._exists_cache = dict()
            return run_info.get_status()

        self.assertEqual(gs(), 'idle_awaiting_cells')

def dictify(s):
    """ Very very dirty minimal YAML parser is OK for testing.
    """
    return dict( l.split(' ', 1) for l in s.split('\n') )

if __name__ == '__main__':
    unittest.main()

