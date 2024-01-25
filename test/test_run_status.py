#!/usr/bin/env python3

import unittest
import sys, os
import glob
from tempfile import mkdtemp
from shutil import rmtree, copytree
from pprint import pprint
import logging as L

from pb_run_status import RunStatus
import yaml

DATA_DIR = os.path.abspath(os.path.dirname(__file__))
VERBOSE = os.environ.get('VERBOSE', '0') != '0'

L.basicConfig(level=(L.DEBUG if VERBOSE else L.WARNING))

class T(unittest.TestCase):

    #Helper functions:
    def use_run(self, run_id, copy=False, make_run_info=True, src="mock"):
        """Inspect a run.
           If copy=True, copies the selected run into a temporary folder first.
           Sets self.current_run to the run id and
           self.runs_dir to the run dir, temporary or otherwise.
           Also returns a RunStatus object for you.
        """
        self.cleanup_run()
        self.data_dir = f"{DATA_DIR}/{src}_examples"

        # Make a temp dir each time
        self.tmp_dir = mkdtemp()
        os.mkdir(self.tmp_dir + '/to')
        if copy:
            self.runs_dir = self.tmp_dir + '/from'
            os.mkdir(self.runs_dir)

            # Clone the run folder into it
            copytree( os.path.join(self.data_dir, run_id),
                      os.path.join(self.runs_dir, run_id),
                      symlinks=True )
        else:
            self.runs_dir = self.data_dir

        # Set the current_run variable
        self.current_run = run_id

        this_run_dir = os.path.join(self.runs_dir, self.current_run)
        if not os.path.exists(this_run_dir):
            raise FileNotFoundError(this_run_dir)

        # Presumably we want to inspect the new run, so do that too.
        # If you want to change files around, do that then make a new RunStatus
        # by copying the line below.
        if make_run_info:
            return RunStatus(this_run_dir,
                             to_location = self.tmp_dir + '/to')

    def cleanup_run(self):
        """If self.tmp_dir has been set, delete the temporary
           folder. Either way, clear the currently set run.
        """
        if vars(self).get('tmp_dir'):
            rmtree(self.tmp_dir)

        self.runs_dir = self.tmp_dir = None
        self.current_run = None

    def tearDown(self):
        """ Avoid leaving temp files around.
        """
        self.cleanup_run()

    def md(self, fp):
        """ Make a directory in the right location
        """
        if fp.startswith('pbpipeline'):
            os.makedirs(os.path.join(self.tmp_dir, 'to', self.current_run, fp))
        else:
            os.makedirs(os.path.join(self.runs_dir, self.current_run, fp))

    def touch(self, fp, content="meh"):
        if fp.startswith('pbpipeline'):
            with open(os.path.join(self.tmp_dir, 'to', self.current_run, fp), 'w') as fh:
                print(content, file=fh)
        else:
            with open(os.path.join(self.runs_dir, self.current_run, fp), 'w') as fh:
                print(content, file=fh)

    def rm(self, dp):
        # Careful with this one, it's basically rm -rf
        try:
            rmtree(os.path.join(self.tmp_dir, 'to', self.current_run, dp))
        except NotADirectoryError:
            os.remove(os.path.join(self.tmp_dir, 'to', self.current_run, dp))
    # And the tests...

    def test_onecell_run(self):
        """ A really basic test
        """
        run_info = self.use_run('r54041_20180613_132039', copy=True)

        self.assertEqual(run_info.get_cells(), {'1_A01': run_info.CELL_PENDING})

        self.touch('1_A01/foo.transferdone')
        run_info._clear_cache()
        self.assertEqual(run_info.get_cells(), {'1_A01': run_info.CELL_READY})

        # Start time should be something (we're not sure what)
        self.assertEqual(len(run_info.get_start_time()), len('Thu Jan  1 01:00:00 1970'))

    def test_run_new(self):
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

    def test_stalled(self):
        """ Test that I can detect a stalled run.
        """
        run_info = self.use_run('r54041_20180518_131155', copy=True)
        self.md('pbpipeline')

        def gs():
            """ Clear the cache and re-read the status. Same as for the
                other tests I really should just make this part of the class.
            """
            run_info._clear_cache()
            return run_info.get_status()

        # With the pipeline dir it's no longer new
        self.assertEqual(gs(), 'idle_awaiting_cells')

        # Now if I set stall_time to 0 (silly but valid) it should be stalled.
        run_info.stall_time = 0

        self.assertEqual(gs(), 'stalled')

    def test_testrun_state(self):
        """ New testrun state is basically the same as aborted but specifically
            for auto-test runs.
        """
        run_info = self.use_run('r64175e_20201211_163702', copy=True)

        self.md('pbpipeline')
        self.touch('pbpipeline/testrun')

        self.assertEqual(run_info.get_status(), 'testrun')

    def test_various_states(self):
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
        self.assertCountEqual( run_info.get_cells_aborted(), "3_D01".split() )
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

    def test_issue_20210608(self):
        """ We seem to have a run with three cells and two are ready to go yet the status is
            'complete' and nothing is happening. Not good!
        """
        run_info = self.use_run('r64175e_20210528_333333', copy=False)

        self.assertCountEqual( run_info.get_cells(), "1_A01  2_B01  3_C01".split() )
        self.assertEqual( run_info.get_status(), 'new' )

        # Now add some output
        self.md('pbpipeline')
        self.touch('pbpipeline/1_A01.done')
        run_info._clear_cache()
        self.assertCountEqual( run_info.get_cells_ready(), "2_B01  3_C01".split() )
        self.assertEqual( run_info.get_status(), 'cell_ready' )

        # Now say the report is done, but there are still cells ready. I don't know how it
        # got in this state but I think the status needs to be 'unknown' as this is not
        # consistent.
        self.touch('pbpipeline/report.done')
        run_info._clear_cache()
        self.assertCountEqual( run_info.get_cells_ready(), "2_B01  3_C01".split() )
        self.assertEqual( run_info.get_status(), 'unknown' )

    def test_error_states(self):
        """ Simulate some pipeline activity on that run.
        """
        run_info = self.use_run('r54041_20180518_131155', copy=False)
        self.md('pbpipeline')

        def gs():
            """ Clear the cache and re-read the status
            """
            run_info._clear_cache()
            return run_info.get_status()

        # If all but 1 have errors we should still await data from the last one
        for cell in "1_B01  2_C01  3_D01  4_E01  5_F01  6_G01".split():
            self.touch(f"pbpipeline/{cell}.failed")

        self.assertEqual(gs(), 'idle_awaiting_cells')

        # If we abort the last one, then that's a fail
        self.touch('pbpipeline/7_H01.aborted')
        self.assertEqual(gs(), 'failed')

    def test_reporting(self):
        """Test the -i flag which I seem to have introduced.
        """
        run_info = self.use_run('r54041_20180613_132039', copy=False)
        self.md('pbpipeline')

        self.touch("pbpipeline/1_A01.done")
        self.touch("pbpipeline/report.started")
        self.assertEqual(run_info.get_status(), 'reporting')

        # Now with -i
        run_info._clear_cache()
        run_info.ignore_report_started = True
        self.assertEqual(run_info.get_status(), 'processed')

    def test_get_yaml(self):
        """The get_yaml() method doesn't (at present) use a YAML library but just prints out
           the lines. Check that, for our simple test at least, it does make valid YAML.
        """
        run_info = self.use_run('r64175e_20210528_333333', copy=False)
        self.md('pbpipeline')
        self.touch('pbpipeline/1_A01.done')
        self.touch('pbpipeline/2_B01.aborted')

        res = run_info.get_yaml()
        res_dict = yaml.safe_load(res)

        self.assertEqual( res_dict,
                          { 'Cells': '1_A01 2_B01 3_C01',
                            'CellsAborted': '2_B01',
                            'CellsDone': '1_A01',
                            'CellsReady': '3_C01',
                            'Instrument': '64175e',
                            'PipelineStatus': 'cell_ready',
                            'RunID': 'r64175e_20210528_333333',
                            'StartTime': 'unknown',
                          } )

    def test_revio(self):
        """Revio runs need some slightly (but not massively) different detection rules
        """
        run_info = self.use_run("r84140_20231018_154254", copy=True, src="revio")

        self.assertEqual(run_info.get_cells(), {'1_C01': run_info.CELL_PENDING,
                                                '1_D01': run_info.CELL_READY})

        self.touch("1_C01/metadata/m84140_231018_155043_s3.transferdone")
        run_info._clear_cache()
        self.assertEqual(run_info.get_cells(), {'1_C01': run_info.CELL_READY,
                                                '1_D01': run_info.CELL_READY})

        # Start time should be something (we're not sure what)
        self.assertEqual(len(run_info.get_start_time()), len('Thu Jan  1 01:00:00 1970'))

    def test_revio_start_time(self):
        """Run r84140_20240116_162812 was coming up with an unknown start time
        """
        run_info = self.use_run("r84140_20240116_162812", copy=False, src="revio")

        # Start time should be some date (we're not sure what as it depends on the file mtime)
        self.assertEqual(len(run_info.get_start_time()), len('Thu Jan  1 01:00:00 1970'))

def dictify(s):
    """ Very very dirty minimal YAML parser is OK for testing.
    """
    return dict( l.split(' ', 1) for l in s.split('\n') )

if __name__ == '__main__':
    unittest.main()

