#!/bin/bash -l
set -euo pipefail
shopt -sq failglob

#  Contents:
#    - Configuration
#    - Logging setup
#    - Python environment
#    - Action callbacks
#    - Utility functions
#    - Scanning loop

#  A driver script that is to be called directly from the CRON. Based on the similar
#  on in Illuminatus.
#
#  It will go through all runs in FROM_LOCATION and take action on them as needed.
#  As a well behaved CRON job it should only output critical error messages
#  to stdout - this is controlled by the MAINLOG setting.
#  The script wants to run every 5 minutes or so, and having multiple instances
#  in flight at once is fine, though in fact there are race conditions possible if two
#  instances start at once and claim the same run for processing (Snakemake locking
#  should catch any fallout before data is scrambled).
#
#  Note within this script I've tried to use ( subshell blocks ) along with "set -e"
#  to emulate eval{} statements in Perl. It does work but you have to be really careful
#  on the syntax, and you have to check $? explicitly - trying to do it implicitly in
#  the manner of ( foo ) || handle_error won't do what you expect.

###--->>> CONFIGURATION <<<---###

# For the sake of the unit tests, we must be able to skip loading the config file,
# so allow the location to be set to, eg. /dev/null
ENVIRON_SH="${ENVIRON_SH:-`dirname $BASH_SOURCE`/environ.sh}"

# This file must provide FROM_LOCATION, TO_LOCATION if not already set.
if [ -e "$ENVIRON_SH" ] ; then
    pushd "`dirname $ENVIRON_SH`" >/dev/null
    source "`basename $ENVIRON_SH`"
    popd >/dev/null
fi

# Tools may reliably use this to report the version of SMRTino being run right now.
# They should look at pbpipeline/start_times to see which versions have touched a given run.
export SMRTINO_VERSION=$(cat "$(dirname $BASH_SOURCE)"/version.txt || echo unknown)

# LOG_DIR is ignored if MAINLOG is set explicitly.
LOG_DIR="${LOG_DIR:-${HOME}/smrtino/logs}"
RUN_NAME_REGEX="${RUN_NAME_REGEX:-r.*_[0-9]{8\}_.*}"

BIN_LOCATION="${BIN_LOCATION:-$(dirname $0)}"
PATH="$(readlink -m $BIN_LOCATION):$PATH"
MAINLOG="${MAINLOG:-${LOG_DIR}/pbpipeline_driver.`date +%Y%m%d`.log}"

# 1) Sanity check these directories exist and complain to STDERR (triggering CRON
#    warning mail) if not.
for d in "${BIN_LOCATION%%:*}" "$FROM_LOCATION" "$TO_LOCATION" ; do
    if ! [ -d "$d" ] ; then
        echo "No such directory '$d'" >&2
        exit 1
    fi
done

# See also the check for a .smrtino marker file below, after logging setup.

###--->>> LOGGING SETUP <<<---###

# 2) Ensure that the directory is there for the main log file and set up logging
#    on file descriptor 5.
if [ "$MAINLOG" = '/dev/stdout' ] ; then
    exec 5>&1
elif [ "$MAINLOG" = '/dev/stderr' ] ; then
    exec 5>&2
else
    mkdir -p "$(dirname "$MAINLOG")" ; exec 5>>"$MAINLOG"
fi

# Main log for general messages (STDERR still goes to the CRON).
log(){ [ $# = 0 ] && cat >&5 || echo "$@" >&5 ; }

# Debug means log only if VERBOSE is set
debug(){ if [ "${VERBOSE:-0}" != 0 ] ; then log "$@" ; else [ $# = 0 ] && cat >/dev/null || true ; fi ; }

# Furthermore $TO_LOCATION must have a .smrtino file in there. I added this as a sanity
# check when moving the pbpipeline dir to the destination, since accidentally pointing
# the pipeline to an empty (or unmounted) directory will cause everything to re-run.
if ! [ -e "$TO_LOCATION"/.smrtino ] ; then
    log "The directory $TO_LOCATION does not contain a .smrtino file."
    echo "The directory $TO_LOCATION does not contain a .smrtino file." >&2
    exit 1
fi

# Per-project log for project progress messages, goes into the output
# directory.
# Unfortunately this can get scrambled if we try to run read1 processing and demux
# at the same time, so have a plog1 for that.
plog() {
    per_run_log="$RUN_OUTPUT/pipeline.log"
    if ! { [ $# = 0 ] && cat >> "$per_run_log" || echo "$*" >> "$per_run_log" ; } ; then
       log '!!'" Failed to write to $per_run_log"
       log "$@"
    fi
}

plog_start() {
    mkdir -vp "$RUN_OUTPUT" |& debug
    plog $'>>>\n>>>\n>>>'" $0 starting action_$STATUS at `date`"
}

# Print a message at the top of the log, and trigger one to print at the end.
intro="`date`. Running $(readlink -f "$0"); PID=$$"
log "====`tr -c '' = <<<"$intro"`==="
log "=== $intro ==="
log "====`tr -c '' = <<<"$intro"`==="
trap 'log "=== `date`. Finished run; PID=$$ ==="' EXIT

###--->>> PYTHON ENVIRONMENT <<<---###

# We always must activate a Python VEnv, unless explicitly set to 'none'
py_venv="${PY3_VENV:-default}"
if [ "${py_venv}" != none ] ; then
    if [ "${py_venv}" = default ] ; then
        log -n "Running `dirname $BASH_SOURCE`/activate_venv ..."
        pushd "`dirname $BASH_SOURCE`" >/dev/null
        source ./activate_venv || { log 'FAILED' ; exit 1 ; }
        popd >/dev/null
    else
        log -n "Activating Python3 VEnv from ${py_venv} ..."
        reset=`set +o | grep -w nounset` ; set +o nounset
        source "${py_venv}/bin/activate" || { log 'FAILED' ; exit 1 ; }
        $reset
    fi
    log 'VEnv ACTIVATED'
fi

###--->>> ACTION CALLBACKS <<<---###

# 3) Define an action for each possible status that a pacbio run can have:

# new)        - this run is seen for the first time (sequencing might be done or still in progress)
# cell_ready) - one or more cells are ready to process
# processed)  - all cells are done and we are ready to make the final report

# Most states require no action, aside from maybe a log message:

# idle_awaiting_cells)  - the run has been picked up by the pipeline but we're waiting for data
# processing_awaiting_cells) - the pipeline is working and we're also waiting for data
# processing) - the pipeline is working and no more data is expected
# reporting)      - the report is being made
# complete)       - the pipeline has finished processing ALL cells on this run and made a report
# aborted)        - the run is not to be processed
# failed)         - the pipeline tried to process the run but failed somewhere
# unknown)        - anything else. ie. something is broken

# All actions can see CELLS STATUS RUNID INSTRUMENT CELLSABORTED as reported by pb_run_status.py, and
# RUN_OUTPUT (the input dir is simply the CWD)
# The cell_ready action can read the CELLSREADY array which is guaranteed to be non-empty

action_new(){
    # Create an output folder with a pbpipe subdir and send an initial notification to RT
    # If this fails we should assume that something is wrong  with the FS and not try to
    # process more runs.
    BREAK=1

    # The symlink ./pbpipeline/from will point back to the data folder
    # There's no symlink back in the other direction to the input folder as we can't write to that FS
    # The logs will be created in the output folder, after which we may use 'plog'
    log "\_NEW $RUNID. Creating $RUN_OUTPUT/pbpipeline folder and making initial report."
    set +e ; ( set -e
      mkdir -vp "$RUN_OUTPUT"/pbpipeline |&debug
      ln -nsv "`pwd -P`" "$RUN_OUTPUT"/pbpipeline/from |& debug

      plog_start
    ) ; [ $? = 0 ] && BREAK=1 || { pipeline_fail New_Run_Setup ; return ; }

    # Run an initial report but don't abort the pipeline if this fails - the error
    # will be noted by the main loop.
    # Note this triggers a summary to be sent to RT as a comment, which should create
    # the new RT ticket.
    run_report "Waiting for cells." "new" | plog && log DONE
}

# TODO - it might be that we don't want to run multiple processings in parallel after all
# In which case split the "cell_ready" state into "idle_cell_ready" and "processing_cell_ready"
# in the state diagram and then only trigger on "idle_cell_ready".
action_cell_ready(){
    # It's time for Snakefile.process_cells to process one or more cells.
    ( cd "$RUN_OUTPUT" &&
      touch $(awk '{ for(i=1; i<=NF; i++) print "pbpipeline/"$i".started" }' <<<"$CELLSREADY") )

    log "\_CELL_READY $RUNID ($CELLSREADY). Kicking off processing."
    plog_start

    # Log the start in a way a script can easily read back (humans can check the main log!)
    save_start_time

    # Do we want an RT message for every cell? No, just a comment.
    send_summary_to_rt comment processing "Cell(s) ready: $CELLSREADY. Report is at" |& plog

    BREAK=1
    plog "Preparing to process cell(s) $CELLSREADY into $RUN_OUTPUT"
    set +e ; ( set -e
      log "  Starting Snakefile.process_cells on $RUNID."
      # pb_run_status.py has sanity-checked that RUN_OUTPUT is the matching directory.
      ( cd "$RUN_OUTPUT"
        Snakefile.process_cells --config cells="$CELLSREADY"
      ) |& plog

      # Now we can have an interim report.
      # FIXME - this may not be safe - two reports running at once!
      run_report "Processing completed for cells $CELLSREADY." "awaiting_cells" | plog && log DONE

      for c in $CELLSREADY ; do
          ( cd "$RUN_OUTPUT" && mv pbpipeline/${c}.started pbpipeline/${c}.done )
      done

    ) |& plog ; [ $? = 0 ] || pipeline_fail Processing_Cells "$CELLSREADY"
}


action_processed() {
    # All cells are processed. Make the final report.
    log "\_PROCESSED $RUNID"
    log "  Now reporting on $RUNID."

    # This touch file puts the run into status reporting.
    # Upload of report is regarded as the final QC step, so if this fails we need to
    # log a failure even if everythign else was OK.
    touch "$RUN_OUTPUT"/pbpipeline/report.started

    # In case we didn't already...
    notify_run_complete

    # FIXME - report aborted vs. good cells!

    BREAK=1
    set +e ; ( set -e
        run_report "All processing complete."
        log "  Completed processing on $RUNID [$CELLS]."

        if [ -s "$RUN_OUTPUT"/pbpipeline/report_upload_url.txt ] ; then
            send_summary_to_rt reply "Finished pipeline" \
                "PacBio pipeline completed on $RUNID and QC report is available at"
            # Final success is contingent on the report upload AND that message going to RT.
            (cd "$RUN_OUTPUT" && mv pbpipeline/report.started pbpipeline/report.done )
        else
            # ||true here avoids calling the error handler twice
            pipeline_fail Report_final_upload || true
        fi
    ) |& plog ; [ $? = 0 ] || pipeline_fail Reporting

}

# Now all the actions that don't do anything (inactions?)

action_idle_awaiting_cells() {
    debug "\_IDLE_AWAITING_CELLS $RUNID"
}

action_processing_awaiting_cells() {
    debug "\_PROCESSING_AWAITING_CELLS $RUNID"
}

action_processing() {
    # At this point we might want to send a notification to RT that all cells are done
    # on the machine. However, there's no guarantee we ever hit this status as it will
    # transition to processed (or error).
    # So I'll call the one-time notification from action_processed too (maybe from failed
    # and aborted too I'm not sure)
    debug "\_PROCESSING $RUNID"

    notify_run_complete
}

action_stalled() {
    # Stalled runs have no activity for $STALL_TIME hours. See doc/failure_and_abort_modes.txt
    # Have ANY cells on this run done anything?
    log "\_STALLED $RUNID"

    BREAK=1 # Maybe not necessary? But we do try to contact RT.
    _matches=''
    for c in $CELLS ; do
        _matches="$_matches`( shopt -s nullglob ; shopt -u failglob ; cd "$RUN_OUTPUT"/pbpipeline && echo ${c}.* )`"
    done

    if [ -z "$_matches" ] ; then
        # Nope - abort the entire run and close the ticket
        echo "no activity for $STALL_TIME hours" > "$RUN_OUTPUT"/pbpipeline/aborted

        # If notifying RT fails don't attempt to do anything else. We can close the ticket manually.
        rt_runticket_manager --no_create --subject aborted --status resolved \
            --comment "No activity in the last $STALL_TIME hours." |& plog
    else
        # So a partial run, we assume. Abort any remaining SMRT cells so the report (or whatever)
        # will be triggered on the next driver cycle
        for c in $CELLS ; do
            _matches=`( shopt -s nullglob ; shopt -u failglob ; cd "$RUN_OUTPUT"/pbpipeline && echo ${c}.* )`

            if [ -z "$_matches" ] ; then
                echo "No activity in the last $STALL_TIME hours." > "$RUN_OUTPUT"/pbpipeline/${c}.aborted
            fi
        done
    fi
}

action_reporting() {
    debug "\_REPORTING $RUNID"
}

action_failed() {
    # failed runs need attention from an operator, so log the situatuion
    set +e
    _reason=`cat "$RUN_OUTPUT"/pbpipeline/failed 2>/dev/null`
    if [ -z "$_reason" ] ; then
        # Get the last lane failure message
        _lastfail=`echo "$RUN_OUTPUT"/pbpipeline/*.failed`
        _reason=`cat ${_lastfail##* } 2>/dev/null`
    fi

    log "\_FAILED $RUNID ($_reason)"
}

action_aborted() {
    # aborted runs are not our concern
    true
}

action_complete() {
    # the pipeline already fully completed for this run - Yay! - nothing to be done ...
    true
}

action_unknown() {
    # this run is broken somehow ... nothing to be done...
    log "\_skipping `pwd` because status is $STATUS"
}

###--->>> UTILITY FUNCTIONS <<<---###

save_start_time(){
    ( echo -n "$SMRTINO_VERSION@" ; date +'%a %b %_d %H:%M:%S %Y' ) \
        >>"$RUN_OUTPUT"/pbpipeline/start_times
}

rt_runticket_manager(){
    rt_runticket_manager.py -r "$RUNID" -Q pbrun "$@"
}

notify_run_complete(){
    # Tell RT that the run finished. This may happen if the last SMRT cell finishes
    # or if remaining cells are aborted. The notification should only happen once.
    if ! [ -e "$RUN_OUTPUT"/pbpipeline/notify_run_complete.done ] ; then

        _cc=`wc -w <<<"$CELLS"`
        _ca=`wc -w <<<"$CELLSABORTED"`
        if [ $_ca -gt 0 ] ; then
            _comment=$(( $_cc - $_ca))" SMRT cells have run. $_ca were aborted. Final report will follow soon."
        else
            _comment="All $_cc SMRT cells have run on the instrument. Final report will follow soon."
        fi
        if rt_runticket_manager --subject processing --reply "$_comment" ; then
            touch "$RUN_OUTPUT"/pbpipeline/notify_run_complete.done
        fi
    fi
}

run_report() {
    # Makes a report. Will not exit on error. I'm assuming all substantial processing
    # will have been done by Snakefile.process_cells

    # usage: run_report [rt_prefix] [rt_run_status] [plog_dest]
    # A blank rt_run_status will leave the status unchanged. A value of "NONE" will
    # suppress reporting to RT entirely.
    # Caller is responsible for log redirection, so this function just prints any
    # progress messages, but the [plog_dest] hint can be used to ensure the right
    # file is referenced when logging error messages.
    set +o | grep '+o errexit' && _ereset='set +e' || _ereset='set -e'
    set +e

    _rprefix="${1:-}"
    _pstatus="${1:-}"
    _rt_run_status="${2:-}"

    if [ "${3:--}" != - ] ; then
        _plog="$3" # Caller may hint where the log is going.
    else
        plog </dev/null #Just to set $per_run_log
        _plog="${per_run_log}"
    fi

    ( cd "$RUN_OUTPUT" ; Snakefile.report -F --config pstatus="$_pstatus" -- report_main ) 2>&1

    # Snag that return value
    _retval=$(( $? + ${_retval:-0} ))

    # Push to server and capture the result (if upload_report.sh does not error it must print a URL)
    # We want stderr from upload_report.sh to go to stdout, so it gets plogged.
    # Note that the code relies on checking the existence of this file to see if the upload worked,
    # so if the upload fails it needs to be removed.
    rm -f "$RUN_OUTPUT"/pbpipeline/report_upload_url.txt
    if [ $_retval = 0 ] ; then
        upload_report.sh "$RUN_OUTPUT" 2>&1 >"$RUN_OUTPUT"/pbpipeline/report_upload_url.txt || \
            { log "Upload error. See $_plog" ;
              rm -f "$RUN_OUTPUT"/pbpipeline/report_upload_url.txt ; }
    fi

    send_summary_to_rt comment "$_rt_run_status" "$_rprefix Run report is at"

    # If this fails, the pipeline will continue, since only the final message to RT
    # is seen as critical.
    if [ $? != 0 ] ; then
        log "Failed to send summary to RT. See $per_run_log"
        _retval=$(( $_retval + 1 ))
    fi

    eval "$_ereset"
    # Retval will be >1 if anything failed. It's up to the caller what to do with this info.
    # The exception is for the upload. Caller should check for the URL file to see if that that failed.
    return $_retval
}

send_summary_to_rt() {
    # Sends a summary to RT. It is assumed that "$RUN_OUTPUT"/pbpipeline/report_upload_url.txt is
    # in place and can be read. In the initial cut, we'll simply list the
    # SMRT cells on the run, as I'm not sure how soon I get to see the XML meta-data?
    # Other than that, supply run_status and premble if you want this.
    _reply_or_comment="${1:-}"
    _run_status="${2:-}"
    _preamble="${3:-Run report is at}"

    # Quoting of a subject with spaces requires use of arrays but beware this:
    # https://stackoverflow.com/questions/7577052/bash-empty-array-expansion-with-set-u
    if [ -n "$_run_status" ] ; then
        _run_status=(--subject "$_run_status")
    else
        _run_status=()
    fi

    echo "Sending new summary of PacBio run to RT."
    # Subshell needed to capture STDERR from make_summary.py
    last_upload_report="`cat "$RUN_OUTPUT"/pbpipeline/report_upload_url.txt 2>/dev/null || echo "Report was not generated or upload failed"`"
    ( set +u ; rt_runticket_manager "${_run_status[@]}" --"${_reply_or_comment}" \
        @<(echo "$_preamble "$'\n'"$last_upload_report" ;
           echo ;
           make_summary.py --runid "$RUNID" --txt - \
           || echo "Error while summarizing run contents." ) ) 2>&1
}

pipeline_fail() {
    # Record a failure of the pipeline. The failure may be due to network outage so try
    # to report to RT but be prepared for that to fail too.

    stage=${1:-Pipeline}

    if [ -z "${2:-}" ] ; then
        # General failure

        # Mark the failure status
        echo "$stage on `date`" > "$RUN_OUTPUT"/pbpipeline/failed

        _failure="$stage failed"
    else
        # Failure of a cell or cells
        for c in $2 ; do
            echo "$stage on `date`" > "$RUN_OUTPUT"/pbpipeline/$c.failed
        done

        _failure="$stage failed for cells [$2]"
    fi

    # Send an alert to RT.
    # Note that after calling 'plog' we can query '$per_run_log' since all shell vars are global.
    plog "Attempting to notify error to RT"
    if rt_runticket_manager --subject failed --reply "$_failure. See log in $per_run_log" |& plog ; then
        log "FAIL $_failure on $RUNID. See $per_run_log"
    else
        # RT failure. Complain to STDERR in the hope this will generate an alert mail via CRON
        msg="FAIL $_failure on $RUNID, and also failed to report the error via RT. See $per_run_log"
        echo "$msg" >&2
        log "$msg"
    fi
}

###--->>> SCANNING LOOP <<<---###

log "Looking for run directories matching regex $FROM_LOCATION/$RUN_NAME_REGEX/"

# 6) Scan through each run until we find something that needs dealing with.
for run in "$FROM_LOCATION"/*/ ; do

  if ! [[ "`basename $run`" =~ ^${RUN_NAME_REGEX}$ ]] ; then
    debug "Ignoring `basename $run`"
    continue
  fi

  # invoke runinfo and collect some meta-information about the run. We're passing this info
  # to the state functions via global variables.
  # This construct allows error output to be seen in the log.
  _runstatus="$(pb_run_status.py "$run")" || pb_run_status.py "$run" | log 2>&1

  # Ugly, but I can't think of a better way...
  RUNID=`grep ^RunID: <<<"$_runstatus"` ;                          RUNID=${RUNID#*: }
  INSTRUMENT=`grep ^Instrument: <<<"$_runstatus"` ;                INSTRUMENT=${INSTRUMENT#*: }
  CELLS=`grep ^Cells: <<<"$_runstatus"` ;                          CELLS=${CELLS#*: }
  CELLSREADY=`grep ^CellsReady: <<<"$_runstatus" || echo ''` ;     CELLSREADY=${CELLSREADY#*: }
  CELLSABORTED=`grep ^CellsAborted: <<<"$_runstatus" || echo ''` ; CELLSABORTED=${CELLSABORTED#*: }
  STATUS=`grep ^PipelineStatus: <<<"$_runstatus"` ;                STATUS=${STATUS#*: }

  if [ "$STATUS" = complete ] || [ "$STATUS" = aborted ] ; then _log=debug ; else _log=log ; fi
  $_log "$run has $RUNID from $INSTRUMENT with cell(s) [$CELLS] and status=$STATUS"

  #Call the appropriate function in the appropriate directory.
  BREAK=0
  RUN_OUTPUT="$TO_LOCATION/$RUNID"
  { pushd "$run" >/dev/null && eval action_"$STATUS" &&
    popd >/dev/null
  } || log "Error while trying to run action_$STATUS on $run"
  #in case this setting got clobbered...
  set -e

  # If the driver started some actual work it should request to break, as the CRON will start
  # a new scan at regular intervals in any case. We don't want an instance of the driver to
  # spend 2 hours processing then start working on a new run. On the other hand, we don't
  # want a problem run to gum up the pipeline if every instance of the script tries to process
  # it, fails, and then exits.
  # Negated test is needed to play nicely with 'set -e'
  ! [ "$BREAK" = 1 ] || break
done
wait
