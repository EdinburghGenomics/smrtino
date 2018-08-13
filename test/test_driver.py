#!/usr/bin/env python3

import unittest
import sys, os, re

import subprocess
from tempfile import mkdtemp
from shutil import rmtree, copytree
from glob import glob

"""Here we're using a Python script to test a shell script (driver.sh).  The shell
   script calls various programs.  Ideally we want to have a cunning way of catching
   and detecting the calls to those programs, similar to the way that Test::Mock works.
   To this end, see the BinMocker class. I've broken this out for general use.
"""
sys.path.insert(0,'.')
from test.binmocker import BinMocker

VERBOSE = os.environ.get('VERBOSE', '0') != '0'
DRIVER = os.path.abspath(os.path.dirname(__file__) + '/../driver.sh')

PROGS_TO_MOCK = """
    Snakefile.process_run Snakefile.report
    rt_runticket_manager.py upload_report.sh
""".split()

class T(unittest.TestCase):

    def setUp(self):
        """Make a shadow folder, and in it have subdirs sequel and pacbio_data and log.
           Initialize BinMocker.
           Calculate the test environment needed to run the driver.sh script.
        """
        self.temp_dir = mkdtemp()
        for d in ['sequel', 'pacbio_data', 'log']:
            os.mkdir(os.path.join(self.temp_dir, d))

        self.bm = BinMocker()
        for p in PROGS_TO_MOCK: self.bm.add_mock(p)

        # Set the driver to run in our test harness. Note I can set
        # $BIN_LOCATION to more than one path.
        # Also we need to set VERBOSE to the driver even if it's not set for this test script.
        self.environment = dict(
                FROM_LOCATION = os.path.join(self.temp_dir, 'sequel'),
                TO_LOCATION = os.path.join(self.temp_dir, 'pacbio_data'),
                BIN_LOCATION = self.bm.mock_bin_dir + ':' + os.path.dirname(DRIVER),
                LOG_DIR = os.path.join(self.temp_dir, 'log'), #this is redundant if...
                MAINLOG = "/dev/stdout",
                ENVIRON_SH = '/dev/null',
                VERBOSE = 'yes',
                PY3_VENV = 'none'
            )

        # Now clear any of these environment variables that might have been set outside
        # of this script.
        for e in self.environment:
            if e in os.environ: del(os.environ[e])

        # See the errors in all their glory
        self.maxDiff = None

    def tearDown(self):
        """Remove the shadow folder and clean up the BinMocker
        """
        rmtree(self.temp_dir)

        self.bm.cleanup()

    def bm_rundriver(self, expected_retval=0, check_stderr=True):
        """A convenience wrapper around self.bm.runscript that sets the environment
           appropriately and runs DRIVER and returns STDOUT split into an array.
        """
        retval = self.bm.runscript(DRIVER, set_path=False, env=self.environment)

        #Where a file is missing it's always useful to see the error.
        #(status 127 is the standard shell return code for a command not found)
        if retval == 127 or VERBOSE:
            print("STDERR:")
            print(self.bm.last_stderr)
        if VERBOSE:
            print("STDOUT:")
            print(self.bm.last_stdout)
            print("RETVAL: %s" % retval)

        self.assertEqual(retval, expected_retval)

        #If the return val is 0 then stderr should normally be empty.
        #An exception would be if scanning one run dir fails but the
        #script continues on to other runs.
        if retval == 0 and check_stderr:
            self.assertEqual(self.bm.last_stderr, '')

        return self.bm.last_stdout.split("\n")

    def copy_run(self, run):
        """Utility function to add a run from mock_examples into TMP/seqdata.
           Returns the path to the run copied.
        """
        run_dir = os.path.join(os.path.dirname(__file__), 'mock_examples', run)

        return copytree(run_dir,
                        os.path.join(self.temp_dir, 'sequel', run),
                        symlinks = True )

    def assertInStdout(self, *words):
        """Assert that there is at least one line in stdout containing all these strings
        """
        o_split = self.bm.last_stdout.split("\n")

        #This loop progressively prunes down the lines, until anything left
        #must have contained each word in the list.
        for w in words:
            o_split = [ l for l in o_split if w in l ]

        self.assertTrue(o_split)

    def shell(self, cmd):
        """Call to os.system in 'safe mode'
        """
        status = os.system("set -euo pipefail ; " + cmd)
        if status:
            raise ChildProcessError("Exit status was %s running command:\n%s" % (status, cmd))

        return status

    ### And the actual tests ###

    def test_nop(self):
        """With no data, nothing should happen. At all.
           The script will exit with status 1 as the glob pattern match will fail.
           Message going to STDERR would trigger an alert from CRON if this happened in production.
        """
        self.bm_rundriver(expected_retval=1)

        self.assertEqual(self.bm.last_calls, self.bm.empty_calls())

        self.assertTrue('no match' in self.bm.last_stderr)

    def test_no_venv(self):
        """With a missing virtualenv the script should fail and not even scan.
           Normally there will be an active virtualenv in the test directory so
           we need to explicitly break this.
        """
        self.environment['PY3_VENV'] = '/dev/null/NO_SUCH_PATH'
        self.bm_rundriver(expected_retval=1)

        self.assertEqual(self.bm.last_calls, self.bm.empty_calls())

        self.assertTrue('/dev/null/NO_SUCH_PATH/bin/activate: Not a directory' in self.bm.last_stderr)
        self.assertFalse('no match' in self.bm.last_stderr)

    def test_no_seqdata(self):
        """If no FROM_LOCATION is set, expect a fast failure.
        """
        test_data = self.copy_run("r54041_20180613_132039")

        self.environment['FROM_LOCATION'] = 'meh'
        self.bm_rundriver(expected_retval=1)
        self.assertEqual(self.bm.last_calls, self.bm.empty_calls())
        self.assertEqual(self.bm.last_stderr, "No such directory 'meh'\n")

        del(self.environment['FROM_LOCATION'])
        self.bm_rundriver(expected_retval=1)
        self.assertEqual(self.bm.last_calls, self.bm.empty_calls())
        self.assertTrue('FROM_LOCATION: unbound variable' in self.bm.last_stderr)

    def test_new(self, test_data=None):
        """A completely new run.  This should gain a ./pbpipeline folder
           which puts it into status idle_awaiting_cells.

           The rt_runticket_manager.py sould be called.

           And there should be a pipeline.log in the ./pbpipeline/output folder.
        """
        if not test_data:
            test_data = self.copy_run("r54041_20180613_132039")

        self.bm_rundriver()

        #Run should be seen
        self.assertInStdout("r54041_20180613_132039", "NEW")

        #Pipeline folder should appear
        self.assertTrue(os.path.isdir(test_data + '/pbpipeline'))

        #Initial report should be made
        expected_calls = self.bm.empty_calls()
        expected_calls['rt_runticket_manager.py'] = ['-r r54041_20180613_132039 -Q pbrun --subject new --comment @???']
        expected_calls['Snakefile.report'] = ['-F --config pstatus=Waiting for cells -- report_main']
        expected_calls['upload_report.sh'] = [self.temp_dir + '/pacbio_data/r54041_20180613_132039']

        #The call to rt_runticket_manager.py is non-deterministic, so we have to doctor it...
        self.bm.last_calls['rt_runticket_manager.py'][0] = re.sub(
                                    r'@\S+$', '@???', self.bm.last_calls['rt_runticket_manager.py'][0] )

        #But nothing else should happen
        self.assertEqual(self.bm.last_calls, expected_calls)

        #Log file should appear (here accessed via the output symlink)
        self.assertTrue(os.path.isfile(test_data + '/pbpipeline/output/pipeline.log') )


    def test_in_pipeline(self):
        """ Run is already processing, nothing to do
        """
        test_data = self.copy_run("r54041_20180613_132039")

        # Mark the run as started, and let's say we're processing read1
        self.shell("mkdir -p " + test_data + "/pbpipeline")
        self.shell("touch " + test_data + "/pbpipeline/1_A01.started")
        self.shell("touch " + test_data + "/pbpipeline/notify_run_complete.done")

        self.bm_rundriver()
        self.assertInStdout("r54041_20180613_132039", "PROCESSING")

        # Nothing should happen
        expected_calls = self.bm.empty_calls()
        self.assertEqual(self.bm.last_calls, expected_calls)

    def test_run_just_finished(self):
        """ Run is already processing, but we do want to notify that
            the run has finished. This is the same as above but without
            the notify_run_complete.done file.
        """
        test_data = self.copy_run("r54041_20180613_132039")

        # Mark the run as started, and let's say we're processing read1
        self.shell("mkdir -p " + test_data + "/pbpipeline")
        self.shell("touch " + test_data + "/pbpipeline/1_A01.started")

        self.bm_rundriver()
        self.assertInStdout("r54041_20180613_132039", "PROCESSING")

        # Message should be sent
        expected_calls = self.bm.empty_calls()
        expected_calls['rt_runticket_manager.py'] = ['-r r54041_20180613_132039 -Q pbrun '
                                                     '--subject processing --reply All SMRT cells '
                                                     'have run on the instrument. Final report will follow soon.']
        self.assertEqual(self.bm.last_calls, expected_calls)

        self.assertTrue(os.path.exists(test_data + "/pbpipeline/notify_run_complete.done"))

if __name__ == '__main__':
    unittest.main()
