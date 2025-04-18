#!/usr/bin/env python3
import os.path
from glob import glob
import sys
import logging as L
import datetime

class RunStatus:
    """This Class provides information about a PacBio sequel run, given a run folder.
       It will parse information from the following sources:
         */*.subreadset.xml ?? for what ??
         Run directory content (including pbpipeline subdir) - to obtain status information
       The status will correspond to a state in the state diagram - see the design doc.
    """
    CELL_PENDING    = 0   # waiting for data from the sequencer
    CELL_READY      = 1   # the pipeline should process this cell now
    CELL_PROCESSING = 2   # the pipeline is working on this cell
    CELL_PROCESSED  = 3   # the pipeline has finished on this cell
    CELL_FAILED     = 4   # the pipeline failed to process this cell
    CELL_ABORTED    = 5   # cell aborted - disregard it
    CELL_TESTRUN    = 6

    def __init__( self, pbrun_dir, opts = '', to_location=None, stall_time=None ):

        # Now that all the touch files are living in the output location, we need to work
        # out both the output location and the input location for this run. The former may
        # not yet exist.
        self.stall_time = int(stall_time) if stall_time is not None else None

        # We need this so we can meaningfully inspect basename(pbrun_dir)
        pbrun_dir = os.path.abspath(pbrun_dir)
        self._assertion_error = False

        if os.path.exists(os.path.join(pbrun_dir, 'pbpipeline', 'from')):
            # ok, pbrun_dir was an existing output directory
            self.from_path = os.path.join(pbrun_dir, 'pbpipeline', 'from')
            self.to_path = pbrun_dir
            L.debug(f"Found {self.from_path}")
        elif to_location:
            L.debug(f"No {pbrun_dir}/pbpipeline/from. Looking in {to_location}")
            if os.path.isdir(os.path.join(to_location,
                                          os.path.basename(pbrun_dir),
                                          'pbpipeline', 'from')):

                # The link we just found should be pointing back to us!
                if not os.path.realpath(
                            os.path.join(to_location,
                                         os.path.basename(pbrun_dir),
                                         'pbpipeline', 'from') )      == os.path.realpath( pbrun_dir ):
                    self._assertion_error = True

                # If the above check works I definitely found the output directory for this run
                self.to_path = os.path.join(to_location, os.path.basename(pbrun_dir))
                self.from_path = pbrun_dir
            else:
                # In that case there should be no directory at all
                if os.path.exists(os.path.join(to_location, os.path.basename(pbrun_dir))):
                    self._assertion_error = True

                # Or else conclude the run is new
                self.to_path = os.path.join(to_location, os.path.basename(pbrun_dir))
                self.from_path = pbrun_dir
        else:
            # We dunno
            raise Exception(f"Location {pbrun_dir} does not look like an output directory and no TO_LOCATION is set.")

        # In quick mode we don't parse the XML. But we don't parse it anyway so this is redundant.
        self.quick_mode = 'q' in opts

        # This is used by the driver to ask what the status of the run would be if the report was not running.
        self.ignore_report_started = 'i' in opts

        self._clear_cache()

    def _clear_cache( self ):
        self._exists_cache = dict()
        self._cells_cache = None

    def _exists_from( self, glob_pattern ):
        """ Returns if a file exists in from_path and caches the result.
        """
        return self._exists(glob_pattern, self.from_path)

    def _exists_to( self, glob_pattern ):
        """ Returns if a file exists in to_path and caches the result.
        """
        return self._exists(glob_pattern, self.to_path)

    def _exists( self, glob_pattern, root_path ):
        """ Returns if a file exists in root_path and caches the result.
            The check will be done with glob() so wildcards can be used, and
            the result will be the number of matches.
        """
        full_pattern = os.path.join(root_path, glob_pattern)
        if full_pattern not in self._exists_cache:
            self._exists_cache[full_pattern] = glob(full_pattern)
            L.debug(f"_exists {full_pattern} => {self._exists_cache[full_pattern]}")

        return len( self._exists_cache[full_pattern] )

    def get_cells( self ):
        """ Returns a dict of { cellname: status } where status is one of the constants
            defined above
            We assume that all of the directories appear right when the run starts, and
            that a .transferdone file signals the cell is ready
        """
        if self._cells_cache is not None:
            return self._cells_cache

        # OK, we need to work it out...
        res = dict()
        cells = glob( os.path.join(self.from_path, '[0-9]_???/') )

        for cell in cells:
            cellname = cell.rstrip('/').split('/')[-1]

            if self._exists_to( f"pbpipeline/{cellname}.aborted" ):
                res[cellname] = self.CELL_ABORTED
            elif self._exists_to( f"pbpipeline/{cellname}.failed" ):
                # Not sure if we need this?
                res[cellname] = self.CELL_FAILED
            elif self._exists_to( f"pbpipeline/{cellname}.done" ):
                res[cellname] = self.CELL_PROCESSED
            elif self._exists_to( f"pbpipeline/{cellname}.started" ):
                res[cellname] = self.CELL_PROCESSING
            elif self._exists_from( f"{cellname}/metadata/*.transferdone" ):
                res[cellname] = self.CELL_READY
            elif self._exists_from( f"{cellname}/*.transferdone" ):
                # Legacy pre-Revio
                res[cellname] = self.CELL_READY
            else:
                res[cellname] = self.CELL_PENDING

        self._cells_cache = res
        return res

    def _was_testrun(self):
        return self._exists_to( 'pbpipeline/testrun' )

    def _was_aborted(self):
        if self._exists_to( 'pbpipeline/aborted' ):
            return True

        # Or if all idividual cells were aborted...
        all_cell_statuses = self.get_cells().values()
        if all_cell_statuses and all( v == self.CELL_ABORTED for v in all_cell_statuses ):
            return True

        return False

    def _is_stalled(self):
        if self.stall_time is None:
            # Nothing is ever stalled then.
            return False

        # Now some datetime tinkering...
        # If I find something dated later than stall_time then this run is not stalled.
        # It's simpler to just get this as a Unix time that I can compare with stat() output.
        stall_time = ( datetime.datetime.now(datetime.timezone.utc)
                       - datetime.timedelta(hours=self.stall_time)
                     ).timestamp()

        for cell in glob( os.path.join(self.from_path, '[0-9]_???') ):

            if os.stat(cell).st_mtime > stall_time:
                # I only need to see one thing
                return False

        # I found no evidence.
        return True

    def get_status( self ):
        """ Work out the status of a run by checking the existence of various touchfiles
            found in the run folder.
            Behaviour with the touchfiles in invalid states is undefined, but we'll always
            report a valid status and in general, if in doubt, we'll report a status that
            does not trigger an action.
            ** This logic is convoluted. Before modifying anything, make a test that reflects
               the change you want to see, then after making the change always run the tests.
               Otherwise you will get bitten in the ass!
        """
        # If one of the sanity checks failed the status must be unknown - any action would
        # be dangerous.
        if self._assertion_error:
            return "unknown"

        # Otherwise, 'new' takes precedence
        if not self._exists_to( 'pbpipeline' ):
            return "new"

        # Auto test pseudo-runs require no processing
        if self._was_testrun():
            return "testrun"
        # Run in aborted state should not be subject to any further processing
        if self._was_aborted():
            return "aborted"

        # At this point we need to know which SMRT cells are ready/done. Disregard aborted cells.
        # If everything was aborted we'll already have decided status='aborted'

        # As with Illuminatus, this logic is a little contorted. The tests reassure me that all is
        # well. If you see a problem add a test case before attempting a fix.

        # No provision for 'redo' state just now, but if there was this would need to
        # go in here to override the failed and complete statuses.
        all_cell_statuses = [ v for v in self.get_cells().values() if v != self.CELL_ABORTED ]

        # If any cell is ready we need to get it processed, regardless of what the report is doing
        # or previous failure.
        if any( v == self.CELL_READY for v in all_cell_statuses ):
            # If we're having issues with parallel processing, we could check that nothing
            # is processing too.
            #if not any( v == self.CELL_PROCESSING for v in all_cell_statuses ):
            #   return "cell_ready"
            return "cell_ready"

        if self._exists_to( 'pbpipeline/report.done' ):
            if self._exists_to( 'pbpipeline/failed' ):
                return "failed"
            elif any( v == self.CELL_READY for v in all_cell_statuses ):
                # Not right - see unit tests
                return "unknown"
            else:
                return "complete"

        if not self.ignore_report_started:
            if self._exists_to( 'pbpipeline/report.started' ):
                # Even if reporting is very quick, we need a state for the run to be in while
                # it is happening. Alternative would be that driver triggers report after processing
                # the last SMRT cell, before marking the cell done, but this seems a bit flakey.
                if self._exists_to( 'pbpipeline/failed' ):
                    return "failed"
                else:
                    return "reporting"

        # The 'failed' flag is going to be set if a report fails to generate or there is an
        # RT error or summat like that.
        # But until the final report is generated, the master 'failed' flag is ignored, so it's
        # possible that an interim report fails but then a new cell gets processed and the report
        # is re-triggered and this time it works and the flag can be cleared. Yeah.

        # If all are processed we're in state processed, and ready to trigger the final report
        if all_cell_statuses and all( v == self.CELL_PROCESSED for v in all_cell_statuses ):
            return "processed"

        # If all cells are processed or failed we're in state failed
        # (otherwise delay failure until all cells are accounted for)
        if all_cell_statuses and all( v in [self.CELL_FAILED, self.CELL_PROCESSED] for v in all_cell_statuses ):
            return "failed"

        # If none are processing we're in state 'idle_awaiting_cells'. This also applies if,
        # for some reason, the list of cells is empty.
        # At this point, we should also check if the run might be stalled.
        if all( v not in [self.CELL_PROCESSING] for v in all_cell_statuses ):
            if self._is_stalled():
                return "stalled"
            else:
                return "idle_awaiting_cells"

        # If any are pending we're in state 'processing_awaiting_cells'
        if any( v == self.CELL_PENDING for v in all_cell_statuses ):
            return "processing_awaiting_cells"

        # Otherwise we're processing but not expecting any more data
        # (we may or may not be processing all the remaining cells)
        return "processing"

    def get_cells_ready(self):
        """ Get a list of the cells which are ready to be processed, if any.
        """
        return [c for c, v in self.get_cells().items() if v == self.CELL_READY]

    def get_cells_processing(self):
        return [c for c, v in self.get_cells().items() if v == self.CELL_PROCESSING]

    def get_cells_aborted(self):
        """ Get a list of the cells that were aborted, if any.
            Note that this is distinct from aborting the whole run, or it being a testrun.
        """
        return [c for c, v in self.get_cells().items() if v == self.CELL_ABORTED]

    def get_cells_done(self):
        return [c for c, v in self.get_cells().items() if v == self.CELL_PROCESSED]

    def get_run_id(self):
        """ We can read this from RunDetails in any of the subreadset.xml files, but it's
            easier to just assume the directory name is the run name. Allow a .xxx extension
            since there are no '.'s is PacBio run names.
        """
        realdir = os.path.basename(os.path.realpath(self.from_path))
        return realdir.split('.')[0]

    def get_instrument(self):
        """ We have only one and the serial number is in the run ID
            We get a more definitive version from the run.metadata.xml file later
        """
        foo = self.get_run_id().split('_')[0]
        if foo.startswith('r') and len(foo) > 1:
            return foo[1:]
        else:
            return 'unknown'

    def get_start_time(self):
        """ Look for the oldest *.txt or *.xml file in any cell directory.

            We could just decode the run ID, but I believe this is the setup
            time rather than the actual run start time.
        """
        txtfiles = [ f for extn in ['txt', 'xml']
                       for subdir in ['/', '/metadata/']
                       for f in
                     glob(os.path.join(self.from_path, f"[0-9]_???{subdir}*.{extn}")) ]

        try:
            oldest_time = min( os.stat(t).st_mtime for t in txtfiles )

            return datetime.datetime.fromtimestamp(oldest_time).ctime()

        except Exception:
            return 'unknown'

    def get_yaml(self, debug=True):
        try:
            return '\n'.join([ 'RunID: '           + self.get_run_id(),
                               'Instrument: '      + self.get_instrument(),
                               'Cells: '           + ' '.join(sorted(self.get_cells())),
                               'CellsReady: '      + ' '.join(sorted(self.get_cells_ready())),
                               'CellsProcessing: ' + ' '.join(sorted(self.get_cells_processing())),
                               'CellsDone: '       + ' '.join(sorted(self.get_cells_done())),
                               'CellsAborted: '    + ' '.join(sorted(self.get_cells_aborted())),
                               'StartTime: '       + self.get_start_time(),
                               'PipelineStatus: '  + self.get_status() ])

        except Exception:
            # if we can't read something just produce a blank reply, unless -d flag
            # is in effect.
            if debug: raise
            pstatus = 'aborted' if self._was_aborted() else 'unknown'

            return '\n'.join([ 'RunID: unknown',
                               'Instrument: unknown',
                               'Cells: ',
                               'CellsReady: ',
                               'CellsProcessing: ',
                               'CellsDone: ',
                               'CellsAborted: ',
                               'StartTime: unknown',
                               'PipelineStatus: ' + pstatus ])

try:
    if __name__ == '__main__':
        # Very cursory option parsing
        # -v = verbose; -d = debug ; -q = quick mode ; -i = ignore report.started
        optind = 1 ; opts = ''
        if sys.argv[optind:] and sys.argv[optind].startswith('-'):
            opts += sys.argv[optind][1:]
            optind += 1

        L.basicConfig( level = L.DEBUG if 'v' in opts else L.WARNING,
                       stream = sys.stderr )

        #If no run specified, examine the CWD.
        runs = sys.argv[optind:] or ['.']
        for run in runs:
            run_info = RunStatus(run, opts,
                                 to_location = os.environ.get('TO_LOCATION'),
                                 stall_time  = os.environ.get('STALL_TIME') or None)
            print ( run_info.get_yaml( debug=('d' in opts) ) )
except BrokenPipeError:
    # We're not fussed
    pass
