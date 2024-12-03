#!/usr/bin/env python3

import unittest
import sys, os, re
from unittest.mock import patch

import subprocess
from tempfile import mkdtemp
from shutil import rmtree, copytree
from glob import glob

"""Here we're using a Python script to test a shell script (driver.sh).  The shell
   script calls various programs.  Ideally we want to have a cunning way of catching
   and detecting the calls to those programs, similar to the way that Test::Mock works.
   To this end, see the BashMocker class. I've broken this out for general use.
"""
from bashmocker import BashMocker

VERBOSE = os.environ.get('VERBOSE', '0') != '0'
DRIVER = os.path.abspath(os.path.dirname(__file__) + '/../driver.sh')

# Note the reason for forcing output to STDERR is to test that any such message
# is being logged and not emitted!
PROGS_TO_MOCK = {
    "Snakefile.process_cells" : True,
    "Snakefile.report"        : True,
    "Snakefile.kinnex_scan"   : True,
    "rt_runticket_manager.py" : "echo STDERR rt_runticket_manager.py >&2",
    "upload_report.sh"        : "echo STDERR upload_report.sh >&2",
    "list_projects_ready.py"  : "echo 00000",
    "date"                    : "echo DATE",
    "mktemp"                  : '[ $# = 1 ] && { touch "$1" ; echo "$1" ;}',
}

class T(unittest.TestCase):

    def setUp(self):
        """Make a shadow folder, and in it have subdirs sequel and pacbio_data and log.
           Initialize BashMocker.
           Calculate the test environment needed to run the driver.sh script.
        """
        self.temp_dir = mkdtemp()
        for d in ['sequel', 'pacbio_data', 'log']:
            os.mkdir(os.path.join(self.temp_dir, d))

        # Touch .smrtino in the output dir
        with open(os.path.join(self.temp_dir, 'pacbio_data', '.smrtino'), 'x'):
            pass

        self.bm = BashMocker()
        for p, s in PROGS_TO_MOCK.items():
            log_calls = (p not in ["date", "mktemp"])
            if type(s) is bool:
                self.bm.add_mock(p, fail=(not s), log=log_calls)
            else:
                self.bm.add_mock(p, side_effect=s, log=log_calls)

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
                PY3_VENV = 'none',
                STALL_TIME = '',
            )

        # Now clear any of these environment variables that might have been set outside
        # of this script.
        for e in self.environment:
            if e in os.environ: del(os.environ[e])

        # See the errors in all their glory
        self.maxDiff = None

    def tearDown(self):
        """Remove the shadow folder and clean up the BashMocker
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

    def copy_run(self, run, src="revio"):
        """Utility function to add a run from mock_examples into TMP/seqdata.
           Returns the path to the run copied.
        """
        self.run_name = run
        run_dir = os.path.join(os.path.dirname(__file__), f"{src}_examples", run)

        # We want to know the expected output location
        self.to_path = os.path.join(self.temp_dir, 'pacbio_data', run)
        self.from_path = os.path.join(self.temp_dir, 'sequel', run)

        # Annoyingly, copytree gives me no way to avoid running copystat on the files.
        # But that doesn't mean it's impossible...
        with patch('shutil.copystat', lambda *a, **kw: True):
            return copytree(run_dir,
                            self.from_path,
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

    def assertNotInStdout(self, *words):
        """Assert that no lines in STDOUT contain all of these strings
        """
        o_split = self.bm.last_stdout.split("\n")

        #This loop progressively prunes down the lines, until anything left
        #must have contained each word in the list.
        for w in words:
            o_split = [ l for l in o_split if w in l ]

        self.assertFalse(o_split)

    def shell(self, cmd):
        """Call to os.system in 'safe mode'
        """
        # Note this now uses subprocess.run since we can thus specify BASH
        status = subprocess.call("set -euo pipefail ; " + cmd, shell=True, executable="/bin/bash")
        if status:
            raise ChildProcessError("Exit status was %s running command:\n%s" % (status, cmd))

        return status

    def rt_cmd(self, *args, nosub=False):
        """Get the expected args to rt_runticket_manager.py
        """
        if nosub:
            return [*f"-r {self.run_name} -Q pbrun".split(), *args]
        else:
            return [*f"-r {self.run_name} -Q pbrun --subject".split(), *args]

    ### And the actual tests ###

    def test_nop(self):
        """With no data, nothing should happen. At all.
           The script will exit with status 1 as the glob pattern match will fail.
           Message going to STDERR would trigger an alert from CRON if this happened in production.
        """
        self.bm_rundriver(expected_retval=1)

        self.assertEqual(self.bm.last_calls, self.bm.empty_calls())

        self.assertTrue('no match' in self.bm.last_stderr)

    def test_no_smrtino_file(self):
        """When the .smrtino file is missing the driver should refuse to proceed.
           Message going to STDERR would trigger an alert from CRON if this happened in production.
        """
        self.shell("rm " + os.path.join(self.temp_dir, 'pacbio_data', '.smrtino'))

        self.bm_rundriver(expected_retval=1)

        self.assertEqual(self.bm.last_calls, self.bm.empty_calls())

        self.assertTrue('does not contain a .smrtino file' in self.bm.last_stderr)
        self.assertTrue('does not contain a .smrtino file' in self.bm.last_stdout)

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
        test_data = self.copy_run("r84140_20231030_134730")

        self.environment['FROM_LOCATION'] = 'meh'
        self.bm_rundriver(expected_retval=1)
        self.assertEqual(self.bm.last_calls, self.bm.empty_calls())
        self.assertEqual(self.bm.last_stderr, "No such directory 'meh'\n")

        del(self.environment['FROM_LOCATION'])
        self.bm_rundriver(expected_retval=1)
        self.assertEqual(self.bm.last_calls, self.bm.empty_calls())
        self.assertTrue('FROM_LOCATION: unbound variable' in self.bm.last_stderr)

    def test_new(self, test_data=None):
        """A completely new run.  The output location should gain a ./pbpipeline folder
           which puts it into status idle_awaiting_cells.

           The rt_runticket_manager.py sould be called.

           And there should be a pipeline.log in the output folder.
        """
        if not test_data:
            test_data = self.copy_run("r84140_20231030_134730")

        self.bm_rundriver()

        # Run should be seen
        self.assertInStdout("r84140_20231030_134730", "NEW")

        # Pipeline folder should appear
        self.assertTrue(os.path.isdir(self.to_path + '/pbpipeline'))

        # No initial report should be made, but 'upload_report.sh' still ends up getting called once
        # because that's the code path
        expected_calls = self.bm.empty_calls()
        expected_calls['rt_runticket_manager.py'] = [self.rt_cmd("new", "--comment", "@???")]
        expected_calls['upload_report.sh'] = [[self.to_path]]

        # The call to rt_runticket_manager.py is non-deterministic, so we have to doctor it...
        self.bm.last_calls['rt_runticket_manager.py'][0][-1] = re.sub(
                                    r'@\S+$', '@???', self.bm.last_calls['rt_runticket_manager.py'][0][-1] )

        self.assertEqual(self.bm.last_calls, expected_calls)

        # Log file should appear (here accessed via the output symlink)
        self.assertTrue(os.path.isfile(f"{self.to_path}/pipeline.log") )

        # And the list of reports uploaded should be empty
        self.assertEqual(0, os.path.getsize(f"{self.to_path}/pbpipeline/report_upload_url.txt"))

    def test_in_pipeline(self):
        """ Run is already processing, nothing to do
        """
        test_data = self.copy_run("r84140_20231030_134730")

        # Mark the run as started, and let's say we're processing read1
        self.shell("mkdir -p " + self.to_path + "/pbpipeline")
        self.shell("cd " + self.to_path + "/pbpipeline && ln -sr " + test_data + " from")
        self.shell("touch " + self.to_path + "/pbpipeline/1_A01.started")
        self.shell("touch " + self.to_path + "/pbpipeline/notify_run_complete.touch")

        self.bm_rundriver()
        self.assertInStdout(self.run_name, "PROCESSING")

        # Nothing should happen
        self.assertEqual(self.bm.last_calls, self.bm.empty_calls())

    def test_run_just_finished(self):
        """ Run is already processing, but we do want to notify that
            the run has finished. This is the same as above but without
            the notify_run_complete.touch file.
        """
        test_data = self.copy_run("r84140_20231030_134730")

        # Mark the run as started, and let's say we're processing cell 1
        self.shell("mkdir -p " + self.to_path + "/pbpipeline")
        self.shell("cd " + self.to_path + "/pbpipeline && ln -sr " + test_data + " from")
        self.shell("touch " + self.to_path + "/pbpipeline/1_A01.started")

        self.bm_rundriver()
        self.assertInStdout(self.run_name, "PROCESSING")
        self.assertNotInStdout("Exception")

        # Message should be sent
        expected_calls = self.bm.empty_calls()
        expected_calls['rt_runticket_manager.py'] = [self.rt_cmd('processing', '--reply',
                                                                 'All 1 SMRT cells have run on the instrument.'
                                                                 ' Final report will follow soon.')]
        self.assertEqual(self.bm.last_calls, expected_calls)

        self.assertTrue(os.path.exists(self.to_path + "/pbpipeline/notify_run_complete.touch"))

    def test_run_was_stalled_1(self):
        """ Simulate a stalled run, which needs to be aborted.
        """
        run = "r84140_20231030_134730"
        test_data = self.copy_run(run)

        self.environment['STALL_TIME'] = '0'
        self.bm_rundriver()
        self.assertInStdout(run, "NEW")
        self.assertTrue(os.path.exists(self.to_path + "/pbpipeline"))

        self.bm_rundriver()
        self.assertInStdout(run, "STALLED")

        expected_calls = self.bm.empty_calls()
        expected_calls['rt_runticket_manager.py'] = [self.rt_cmd(
                                                       'aborted', '--no_create', '--status', 'resolved',
                                                       '--comment', 'No activity in the last 0 hours.' )]
        self.assertEqual(self.bm.last_calls, expected_calls)

        # Now it should be aborted - since we're in verbose mode we do see this,
        self.bm_rundriver()
        self.assertInStdout(run, 'status=aborted')

    def test_run_was_stalled_2(self):
        """ Simulate a stalled run, which has partially worked.
        """
        run = "r84140_20231018_154254"

        # Copy run which has 1 cell ready, one pending. Make the ready cell done.
        test_data = self.copy_run(run)
        self.shell("mkdir -p " + self.to_path + "/pbpipeline")
        self.shell("cd " + self.to_path + "/pbpipeline && ln -sr " + test_data + " from")
        self.shell("touch " + self.to_path + "/pbpipeline/1_D01.done")

        self.environment['STALL_TIME'] = '1'
        self.bm_rundriver()
        self.assertInStdout(run, "IDLE_AWAITING_CELLS")

        self.environment['STALL_TIME'] = '0'
        self.bm_rundriver()
        self.assertInStdout(run, "STALLED")

        # A this point, nothing much should happen. (flags are written to pbpipeline)
        self.assertEqual(self.bm.last_calls, self.bm.empty_calls())

        # But on the next round, it should complete
        # Except that 'upload_report.sh' will appear to fail, so there will be an error.
        # I could add a side effect to the call, maybe.
        self.bm_rundriver()
        self.assertInStdout(run, "PROCESSED")

        # The second to rt_runticket_manager.py is non-deterministic, so we have to doctor it...
        last_reply_fd = self.bm.last_calls['rt_runticket_manager.py'][-1][-1]

        expected_calls = self.bm.empty_calls()
        expected_calls['Snakefile.report'] = [ ['-p', 'report_main'] ]
        expected_calls['upload_report.sh'] = [[self.to_path]]
        expected_calls['rt_runticket_manager.py'] = [self.rt_cmd( 'processing',
                                                       '--reply',
                                                       '1 SMRT cells have run. 1 were aborted. Final report will follow soon.' ),
                                                     self.rt_cmd( 'Finished pipeline',
                                                       '--reply', last_reply_fd )]
        expected_calls['list_projects_ready.py'] = [[]]
        self.assertEqual(self.bm.last_calls, expected_calls)
        self.assertTrue(os.path.exists(self.to_path + "/pbpipeline/notify_run_complete.touch"))

        # Now it should be in status COMPLETE because run of the cells did work
        # (note this check relies on driver.sh always being run in VERBOSE mode)
        self.bm_rundriver()
        self.assertEqual(self.bm.last_calls, self.bm.empty_calls())
        self.assertInStdout(run, "status=complete")

    def test_process_run_partial(self):
        """ Test processing a run when one cell is ready
        """
        test_data = self.copy_run("r84140_20231018_154254")

        # Run the pipeline once to setup the output directory
        self.bm_rundriver()

        # Run again to try processing the cells
        self.bm_rundriver()

        # This was appearing in some cases
        self.assertNotInStdout("Exception")

        # Check the touch files all appear
        for cell in "1_D01".split():
            self.assertTrue(os.path.exists(f"{self.to_path}/pbpipeline/{cell}.done"))
        for cell in "1_C01".split():
            self.assertFalse(os.path.exists(f"{self.to_path}/pbpipeline/{cell}.done"))

        # Snakemake process_cells should have been started on just one cell
        self.assertEqual(self.bm.last_calls['Snakefile.process_cells'],
                         [ [ "-R", "one_cell_info", "one_barcode_info", "list_blob_plots",
                             "--config", "cells=1_D01",
                                         "sc_data=sc_data.DATE.XXX.yaml",
                                         "blobs=1",
                                         "cleanup=0",
                                         "quick=1",
                             "-p" ],
                           [ "-R", "one_cell_info", "one_barcode_info", "list_blob_plots",
                             "--config", "cells=1_D01",
                                         "sc_data=sc_data.DATE.XXX.yaml",
                                         "blobs=1",
                                         "cleanup=1",
                                         "quick=0",
                             "-p" ], ])

        # Report should be made on just the one cell too
        self.assertEqual(self.bm.last_calls['Snakefile.report'],
                         [ ["-R", "make_report",
                            "--config", "cells=1_D01", "sc_data=sc_data.DATE.XXX.yaml",
                            "-p", "report_main"] ])

        for r in "report.started report.done".split():
            self.assertFalse(os.path.exists(f"{self.to_path}/pbpipeline/{r}"))

    def test_process_run_ok(self):
        """ Test processing a run when the cells are ready
        """
        test_data = self.copy_run("r84140_20231018_154254")
        self.shell(f"touch {self.from_path}/1_C01/metadata/m84140_231018_155043_s3.transferdone")
        self.shell(f"touch {self.from_path}/1_D01/metadata/m84140_231018_162059_s4.transferdone")

        # Run the pipeline once to setup the output directory
        self.bm_rundriver()

        # Run again to try processing the cells
        self.bm_rundriver()

        # This was appearing in some cases
        self.assertNotInStdout("Exception")

        # Check the touch files all appear
        for cell in "1_C01 1_D01".split():
            self.assertTrue(os.path.exists(f"{self.to_path}/pbpipeline/{cell}.done"))

        # Check the right things were called.
        self.assertEqual(self.bm.last_calls["Snakefile.report"],
                         [ ["-R", "make_report",
                            '--config', "cells=1_C01 1_D01", "sc_data=sc_data.DATE.XXX.yaml",
                            "-p", "report_main"] ])


    def test_process_run_fail(self):
        """ Test error handling when Snakefile.process_cells fails
        """
        test_data = self.copy_run("r84140_20231018_154254")
        self.shell(f"touch {self.from_path}/1_C01/metadata/m84140_231018_155043_s3.transferdone")
        self.shell(f"touch {self.from_path}/1_D01/metadata/m84140_231018_162059_s4.transferdone")

        self.bm.add_mock("Snakefile.process_cells", fail=True)

        # Run the pipeline once to setup the output directory
        self.bm_rundriver()

        # Run again to try processing the cells
        self.bm_rundriver()

        # Why am I seeing a broken pipe error? There was a logic problem
        self.assertNotInStdout("Exception")

        # Check the touch files all appear
        if VERBOSE:
            os.system(f"ls {self.to_path}/pbpipeline")

        for cell in "1_C01 1_D01".split():
            for sf in "started failed".split():
                self.assertTrue(os.path.exists(f"{self.to_path}/pbpipeline/{cell}.{sf}"))

        # Check that upload_reports.sh is not called
        expected_calls = self.bm.empty_calls()

        expected_calls['Snakefile.kinnex_scan'] = [["--config", "cells=1_C01 1_D01", "sc_data=sc_data.DATE.XXX.yaml",
                                                    '-p']]
        expected_calls['Snakefile.process_cells'] = [[ "-R", "one_cell_info", "one_barcode_info", "list_blob_plots",
                                                       "--config", "cells=1_C01 1_D01",
                                                                   "sc_data=sc_data.DATE.XXX.yaml",
                                                                   "blobs=1",
                                                                   "cleanup=0",
                                                                   "quick=1",
                                                       "-p" ]]
        expected_calls['rt_runticket_manager.py'] = [self.rt_cmd("processing", "--comment", "@???"),
                                                     self.rt_cmd("failed", "--reply",
                                                                  "Processing_cells failed for cells [1_C01 1_D01].\n"
                                                                  f"See log in {self.to_path}/pipeline.log") ]

        # Doctor self.bm.last_calls because we don't know the FD
        for cl in self.bm.last_calls['rt_runticket_manager.py']:
            if cl[-1].startswith('@/'):
                cl.pop()
                cl.append('@???')

        self.assertEqual(self.bm.last_calls, expected_calls)

    def test_process_run_rsync_fail(self):
        """ Test error handling when all is well but rsync fails
        """
        test_data = self.copy_run("r84140_20231018_154254")
        self.shell(f"touch {self.from_path}/1_C01/metadata/m84140_231018_155043_s3.transferdone")
        self.shell(f"touch {self.from_path}/1_D01/metadata/m84140_231018_162059_s4.transferdone")

        self.bm.add_mock("upload_report.sh", fail=True)

        # Run the pipeline once to setup the output directory, then to process the cells
        self.bm_rundriver()
        self.bm_rundriver()

        # Check this, just in case
        self.assertNotInStdout("Exception")

        # Check the touch files all appear
        if VERBOSE:
            os.system(f"ls {self.to_path}/pbpipeline")

        for cell in "1_C01 1_D01".split():
            self.assertTrue(os.path.exists(f"{self.to_path}/pbpipeline/{cell}.done"))

        self.assertTrue(os.path.exists(f"{self.to_path}/pbpipeline/failed"))

        # Check that upload_reports.sh is called
        expected_calls = self.bm.empty_calls()

        expected_calls['upload_report.sh'] = [[self.to_path]]
        expected_calls['list_projects_ready.py'] = [[]]

        expected_calls['Snakefile.process_cells'] = [[ "-R", "one_cell_info", "one_barcode_info", "list_blob_plots",
                                                       "--config", "cells=1_C01 1_D01",
                                                                   "sc_data=sc_data.DATE.XXX.yaml",
                                                                   "blobs=1",
                                                                   "cleanup=0",
                                                                   "quick=1",
                                                       "-p" ],
                                                    [ "-R", "one_cell_info", "one_barcode_info", "list_blob_plots",
                                                       "--config", "cells=1_C01 1_D01",
                                                                   "sc_data=sc_data.DATE.XXX.yaml",
                                                                   "blobs=1",
                                                                   "cleanup=1",
                                                                   "quick=0",
                                                       "-p" ]]
        expected_calls['Snakefile.report'] = [[ "-R", "make_report",
                                                "--config", "cells=1_C01 1_D01", "sc_data=sc_data.DATE.XXX.yaml",
                                                "-p", "report_main"]]

        expected_calls['Snakefile.kinnex_scan'] = [["--config", "cells=1_C01 1_D01", "sc_data=sc_data.DATE.XXX.yaml",
                                                    "-p"]]

        # Ideally the "All 2 SMRT cells have run" message would be sent before the processing starts, but
        # in real use the notification will trigger on the next CRON run so this is a quirk not a bug.
        expected_calls['rt_runticket_manager.py'] = [self.rt_cmd("processing", "--comment", "@???"),
                                                     self.rt_cmd("--comment",
                                                                 "Finished quick processing for cells 1_C01 1_D01.",
                                                                 nosub = True),
                                                     self.rt_cmd("processing", "--reply",
                                                                  "All 2 SMRT cells have run on the instrument. "
                                                                  "Final report will follow soon."),
                                                     self.rt_cmd("failed", "--reply",
                                                                  "Report_final_upload failed.\n"
                                                                  f"See log in {self.to_path}/pipeline.log") ]

        # Doctor self.bm.last_calls because we don't know the FD
        for cl in self.bm.last_calls['rt_runticket_manager.py']:
            if cl[-1].startswith('@/'):
                cl.pop()
                cl.append('@???')

        self.assertEqual(self.bm.last_calls, expected_calls)


if __name__ == '__main__':
    unittest.main()
