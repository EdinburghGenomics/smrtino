#!/usr/bin/env python3

import unittest
import sys, os
import glob
from tempfile import mkdtemp
from shutil import rmtree, copytree
from pprint import pprint
import logging as L


# Adding this to sys.path makes the test work if you just run it directly.
sys.path.insert(0,'.')
from pb_run_status import RunStatus

DATA_DIR = os.path.abspath(os.path.dirname(__file__) + '/status_check_examples')
VERBOSE = os.environ.get('VERBOSE', '0') != '0'

L.basicConfig(level=(L.DEBUG if VERBOSE else L.WARNING))

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

    def test_onecell_run( self ):
        """ A really basic test
        """
        run_info = self.use_run('r54041_20180613_132039', copy=True)

        self.assertEqual(run_info.get_cells(), {'1_A01': run_info.CELL_PENDING})

        self.touch('1_A01/foo.transferdone')
        run_info._clear_cache()
        self.assertEqual(run_info.get_cells(), {'1_A01': run_info.CELL_READY})

    def test_run_new( self ):
        """ A totally new run.
        """
        run_info = self.use_run('r54041_20180518_131155')

        self.assertEqual( run_info.get_status(), 'new' )

        # I should get the same via YAML
        self.assertEqual( dictify(run_info.get_yaml())['PipelineStatus:'], 'new' )

        # This run has 7 cells
        self.assertCountEqual( run_info.get_cells(), "1_B01  2_C01  3_D01  4_E01  5_F01  6_G01  7_H01".split() )

        # None are ready
        self.assertCountEqual( run_info.get_cells_ready(), [] )

    def test_various_states( self ):
        """ Simulate some pipeline activity on that run.
        """
        run_info = self.use_run('r54041_20180518_131155', copy=True)
        self.md('pbpipeline')

        def gs():
            """ Clear the cache and re-read the status
            """
            run_info._clear_cache()
            return run_info.get_status()

        # With the pipeline dir it's no longer new
        self.assertEqual(gs(), 'idle_awaiting_cells')

        # Let a couple of SMRT cells finish
        self.touch('1_B01/foo.transferdone')
        self.touch('2_C01/foo.transferdone')

        self.assertEqual(gs(), 'cell_ready')
        self.assertCountEqual( run_info.get_cells_ready(), ["1_B01", "2_C01"])

        # Start one of them
        self.touch('pbpipeline/1_B01.started')
        self.assertEqual(gs(), 'cell_ready')

        # And the other
        self.touch('pbpipeline/2_C01.started')
        self.assertEqual(gs(), 'processing_awaiting_cells')

        # Finishing just one should make no difference
        self.touch('pbpipeline/2_C01.done')
        self.assertEqual(gs(), 'processing_awaiting_cells')

        # Finishing both...
        self.touch('pbpipeline/1_B01.done')
        self.assertEqual(gs(), 'idle_awaiting_cells')

        # Abort the next one
        self.touch('3_D01/foo.transferdone')
        self.assertEqual(gs(), 'cell_ready')
        self.assertCountEqual( run_info.get_cells_ready(), ["3_D01"])

        self.touch('pbpipeline/3_D01.aborted')

        # It should vanish from the list of ready cells (but not the full list)
        self.assertEqual(gs(), 'idle_awaiting_cells')
        self.assertCountEqual( run_info.get_cells(), "1_B01 2_C01 3_D01 4_E01 5_F01 6_G01 7_H01".split() )
        self.assertCountEqual( run_info.get_cells_ready(), [] )

        # Finish the next three
        self.touch('pbpipeline/4_E01.done')
        self.touch('pbpipeline/5_F01.done')
        self.touch('pbpipeline/6_G01.done')

        self.assertEqual(gs(), 'idle_awaiting_cells')

        # And start the last one
        self.touch('pbpipeline/7_H01.started')
        self.assertEqual(gs(), 'processing')

        # And complete it
        self.touch('pbpipeline/7_H01.done')
        self.assertEqual(gs(), 'processed')


    def test_error_states( self ):
        """ Simulate some pipeline activity on that run.
        """
        run_info = self.use_run('r54041_20180518_131155', copy=True)
        self.md('pbpipeline')

        def gs():
            """ Clear the cache and re-read the status
            """
            run_info._clear_cache()
            return run_info.get_status()

        # If all but 1 have errors we should still await data from the last one
        for cell in "1_B01  2_C01  3_D01  4_E01  5_F01  6_G01".split():
            self.touch('pbpipeline/' + cell + '.failed')

        self.assertEqual(gs(), 'idle_awaiting_cells')

        # If we abort the last one, then that's a fail
        self.touch('pbpipeline/7_H01.aborted')
        self.assertEqual(gs(), 'failed')

def dictify(s):
    """ Very very dirty minimal YAML parser is OK for testing.
    """
    return dict( l.split(' ', 1) for l in s.split('\n') )

if __name__ == '__main__':
    unittest.main()

