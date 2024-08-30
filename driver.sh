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

# Canonicalize the path.
BASH_SRC="$(readlink -f "$BASH_SOURCE")"
BASH_DIR="$(dirname "$BASH_SRC")"

# For the sake of the unit tests, we must be able to skip loading the config file,
# so allow the location to be set to, eg. /dev/null
ENVIRON_SH="${ENVIRON_SH:-$BASH_DIR/environ.sh}"

# This file must provide FROM_LOCATION, TO_LOCATION if not already set.
if [ -e "$ENVIRON_SH" ] ; then
    pushd "`dirname $ENVIRON_SH`" >/dev/null
    source "`basename $ENVIRON_SH`"
    popd >/dev/null

    # Saves having to put 'export' on every line in the config.
    export CLUSTER_PARTITION  FROM_LOCATION      TO_LOCATION \
           RT_SYSTEM          RT_SETTINGS        GENOLOGICSRC \
           PROJECT_NAME_LIST  PROJECT_PAGE_URL   REPORT_DESTINATION  REPORT_LINK \
           RSYNC_CMD          STALL_TIME         VERBOSE    \
           FILTER_LOCALLY     BLOBS \
           EXTRA_SNAKE_FLAGS  EXTRA_SNAKE_CONFIG EXTRA_SLURM_FLAGS \
           SMRTLINKRC_SECTION
fi

# LOG_DIR is ignored if MAINLOG is set explicitly.
LOG_DIR="${LOG_DIR:-${HOME}/smrtino/logs}"
RUN_NAME_REGEX="${RUN_NAME_REGEX:-r.*_[0-9]{8\}_.*}"

BIN_LOCATION="${BIN_LOCATION:-$BASH_DIR}"
PATH="$(readlink -m $BIN_LOCATION):$PATH"
MAINLOG="${MAINLOG:-${LOG_DIR}/smrtino_driver.`date +%Y%m%d`.log}"

# Tools may reliably use this to report the version of SMRTino being run right now.
# They should look at pbpipeline/start_times to see which versions have touched a given run.
export SMRTINO_VERSION=$(smrtino_version.py)

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
debug() {
    if [ "${VERBOSE:-0}" != 0 ] ; then
        log "$@"
    else
        [ $# = 0 ] && cat >/dev/null || true
    fi
}

# Furthermore $TO_LOCATION must have a .smrtino file in there. I added this as a sanity
# check when moving the pbpipeline dir to the destination, since accidentally pointing
# the pipeline to an empty (or unmounted) directory will cause everything to re-run.
if ! [ -e "$TO_LOCATION"/.smrtino ] ; then
    log "The directory $TO_LOCATION does not contain a .smrtino file."
    echo "The directory $TO_LOCATION does not contain a .smrtino file." >&2
    exit 1
fi

# Per-run log for detailed progress messages, goes into the output directory.
plog() {
    per_run_log="$RUN_OUTPUT/pipeline.log"
    if ! { [ $# = 0 ] && cat >> "$per_run_log" || echo "$*" >> "$per_run_log" ; } ; then
       log '!!'" Failed to write to $per_run_log"
       log "$@"
    fi
}

plog_start() {
    mkdir -vp "$RUN_OUTPUT" |& debug
    plog $'>>>\n>>>\n>>>'" $BASH_SRC starting action_$STATUS at `date`"
}

# Print a message at the top of the log, and trigger one to print at the end.
intro="`date`. Running $BASH_SRC; PID=$$"
log "====`tr -c '' = <<<"$intro"`==="
log "=== $intro ==="
log "====`tr -c '' = <<<"$intro"`==="
trap 'log "=== `date`. Finished run; PID=$$ ==="' EXIT

###--->>> PYTHON ENVIRONMENT <<<---###

# We always must activate a Python VEnv, unless explicitly set to 'none'
py_venv="${PY3_VENV:-default}"
if [ "${py_venv}" != none ] ; then
    if [ "${py_venv}" = default ] ; then
        log -n "Running $BASH_DIR/activate_venv ..."
        pushd "$BASH_DIR" >/dev/null
        source ./activate_venv >&5 || { log 'FAILED' ; exit 1 ; }
        popd >/dev/null
    else
        log -n "Activating Python3 VEnv from ${py_venv} ..."
        reset=`set +o | grep -w nounset` ; set +o nounset
        source "${py_venv}/bin/activate" || { log 'FAILED' ; exit 1 ; }
        $reset
    fi
    log 'VEnv ACTIVATED'
fi

###--->>> UTILITY FUNCTIONS USED BY THE ACTIONS <<<---###

touch_atomic(){
    # Create a file but it's an error if the file already existed.
    (set -o noclobber ; >"$1")
}

touch_or_wait(){
    # Create a file but if it already exists poll for up to 5 minutes
    poll_interval=5 # seconds
    poll_count=60   # 60 loops == 5 minutes

    while [[ $poll_count -gt 0 ]] ; do
        poll_count=$(( $poll_count - 1 ))
        (set -o noclobber ; >"$1") || continue
        return 0
    done
    echo "Timeout after 300 seconds." 2>&1
    return 1
}

mv_atomic(){
    # Used in place of "mv x.started x.done" and fails if the target exists.
    # Doesn't actually move the file, just makes a new empty file.
    echo "renaming $1 -> $2"
    (set -o noclobber ; >"$2") && rm "$1"
}

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
# testrun)        - ditto
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
    log "\_NEW $RUNID. Creating $RUN_OUTPUT/pbpipeline directory and RT ticket."
    set +e ; ( set -e
      mkdir -vp "$RUN_OUTPUT"/pbpipeline |&debug
      ln -nsv "`pwd -P`" "$RUN_OUTPUT"/pbpipeline/from |& debug

      plog_start
    )
    if [ $? != 0 ] ; then
        pipeline_fail New_run_setup
        return
    fi

    # Trigger a summary to be sent to RT as a comment, which should create
    # the new RT ticket.
    # Do this via upload_reports even though there will be 0 reports.
    upload_reports NEW |& plog
    log DONE
}

# TODO - it might be that we don't want to run multiple processings in parallel after all
# In which case split the "cell_ready" state into "idle_cell_ready" and "processing_cell_ready"
# in the state diagram and then only trigger on "idle_cell_ready".
action_cell_ready(){
    # It's time for Snakefile.process_cells to process one or more cells.
    local cell always_run
    for cell in $CELLSREADY ; do
        touch_atomic "$RUN_OUTPUT"/pbpipeline/${cell}.started
    done

    log "\_CELL_READY $RUNID ($CELLSREADY). Kicking off processing."
    plog_start

    # Log the start in a way a script can easily read back (humans can check the main log!)
    save_start_time

    # Do we want an RT message for every cell? Well, just a comment. And continue on error.
    set +e
    send_summary_to_rt comment processing "Cell(s) ready to process: $CELLSREADY." |& plog

    # If $CELLSREADY + $CELLSDONE + $CELLSABORTED == $CELLS then this will complete the run.
    # If $CELLSPROCESSING is non-empty, we can't be sure if those will finish first.

    BREAK=1
    plog "Preparing to process cell(s) $CELLSREADY into $RUN_OUTPUT"
    set +e ; ( set -e
      log "  Starting Snakefile.process_cells on $RUNID."

      # pb_run_status.py has sanity-checked that RUN_OUTPUT is the matching directory.
      cd "$RUN_OUTPUT"

      # Compile info for all cells, not just the one being processed.
      scan_cells.py -c $CELLSREADY $CELLSPROCESSING $CELLSDONE > sc_data.yaml

      always_run=(one_cell_info one_barcode_info list_blob_plots)
      Snakefile.process_cells -R "${always_run[@]}" \
                              --config cells="$CELLSREADY" blobs="${BLOBS:-1}" cleanup=1 \
                                       ${EXTRA_SNAKE_CONFIG:-} \
                              -p |& plog

      # Now we can have a report. This bit runs locally.
      plog "Processing done. Now for Snakefile.report"

      always_run=(make_report)
      Snakefile.report -R "${always_run[@]}" \
                       --config cells="$CELLSREADY" -p report_main |& plog

      touch_or_wait pbpipeline/report.started
      for cell in $CELLSREADY ; do
          mv_atomic pbpipeline/${cell}.started pbpipeline/${cell}.done
      done

      # Making projects_ready.txt is outside of the Snakefile now, and must
      # be done after fixing the touch files.
      list_projects_ready.py > projects_ready.txt

    ) |& plog
    if [ $? != 0 ] ; then
        pipeline_fail Processing_cells "$CELLSREADY"
        return
    fi

    # And upload the reports. If all cells are done, go directly to action_processed
    plog "Processing and reporting done for cells $CELLSREADY. Uploading reports."
    if pb_run_status.py -i "$RUN_OUTPUT" | grep -qFx 'PipelineStatus: processed'  ; then
        # In case we didn't already...
        notify_run_complete |& plog

        set +e ; ( set -e
            upload_reports FINAL
            cd "$RUN_OUTPUT"
            mv_atomic pbpipeline/report.started pbpipeline/report.done
        ) |& plog ; [ $? = 0 ] || pipeline_fail Report_final_upload
        log "  Completed processing on $RUNID [$CELLS]."
    else
        # If this fails now, action_processed may still rectify things later.
        if ! upload_reports INTERIM |& plog ; then
            plog "Error uploading reports"
            log  "Error uploading reports"
        fi
        log DONE
    fi
    # Last-ditch cleanup.
    ( cd "$RUN_OUTPUT" && rm -f pbpipeline/report.started )

}

action_processed() {
    # All cells are processed and reported. Normally this is short-circuited by the
    # end of reporting the final cell, but it need not be (eg. if final cell is aborted
    # or if there was an intermittent upload failure).
    # Cells are processed as we go, so there is little to be done.
    log "\_PROCESSED $RUNID"
    log "  Now finalising $RUNID."

    # This touch file puts the run into status reporting.
    # Upload of all reports is regarded as the final QC step, so if this fails we need to
    # log a failure even if everything else was OK.
    touch_atomic "$RUN_OUTPUT"/pbpipeline/report.started
    BREAK=1
    set +e

    # In case we didn't already...
    notify_run_complete |& plog

    set +e ; ( set -e
        cd "$RUN_OUTPUT"

        Snakefile.report -p report_main
        list_projects_ready.py > projects_ready.txt
    ) |& plog ; [ $? = 0 ] || pipeline_fail Final_report

    set +e ; ( set -e
        upload_reports FINAL
    ) |& plog ; [ $? = 0 ] || pipeline_fail Report_final_upload

    # Final success is contingent on the report upload AND that message going to RT.
    ( cd "$RUN_OUTPUT" && mv_atomic pbpipeline/report.started pbpipeline/report.done )
    log "  Completed processing on $RUNID [$CELLS]."
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

    notify_run_complete |& plog
}

action_reporting() {
    debug "\_REPORTING $RUNID"
}

action_failed() {
    # failed runs need attention from an operator, so log the situatuion
    set +e
    local lastfail
    local reason=`cat "$RUN_OUTPUT"/pbpipeline/failed 2>/dev/null`
    if [ -z "$reason" ] ; then
        # Get the last lane failure message
        lastfail=`echo "$RUN_OUTPUT"/pbpipeline/*.failed`
        reason=`cat ${lastfail##* } 2>/dev/null`
    fi

    log "\_FAILED $RUNID ($reason)"
}

action_stalled() {
    # Stalled runs have no activity for $STALL_TIME hours. See doc/failure_and_abort_modes.txt
    # Have ANY cells on this run done anything?
    log "\_STALLED $RUNID"

    BREAK=1 # Maybe not necessary? But we do try to contact RT.
    local matches=''
    for c in $CELLS ; do
        matches="$matches`( shopt -s nullglob ; shopt -u failglob ; cd "$RUN_OUTPUT"/pbpipeline && echo ${c}.* )`"
    done

    if [ -z "$matches" ] ; then
        # Nope - abort the entire run and close the ticket
        echo "no activity for $STALL_TIME hours" > "$RUN_OUTPUT"/pbpipeline/aborted

        # If notifying RT fails don't attempt to do anything else. We can close the ticket manually.
        rt_runticket_manager --subject aborted --no_create --status resolved \
            --comment "No activity in the last $STALL_TIME hours." |& plog
    else
        # So a partial run, we assume. Abort any remaining SMRT cells so the report (or whatever)
        # will be triggered on the next driver cycle
        for c in $CELLS ; do
            matches=`( shopt -s nullglob ; shopt -u failglob ; cd "$RUN_OUTPUT"/pbpipeline && echo ${c}.* )`

            if [ -z "$matches" ] ; then
                echo "No activity in the last $STALL_TIME hours." > "$RUN_OUTPUT"/pbpipeline/${c}.aborted
            fi
        done
    fi
}

action_aborted() {
    # aborted runs are not our concern
    true
}

action_testrun() {
    # self-test pseudo runs also require no further reporting
    # Note that on the Revio we don't seem to have test runs like this, but we can still
    # manually flag a run as a test.
    true
}

action_complete() {
    # the pipeline already fully completed for this run - Yay!
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

# Wrapper for ticket manager that sets the run and queue
rt_runticket_manager(){
    rt_runticket_manager.py -r "$RUNID" -Q pbrun "$@"
}

notify_run_complete(){
    # Tell RT that the run finished. This may happen if the last SMRT cell finishes
    # or if remaining cells are aborted. The notification should only happen once.
    if ! [ -e "$RUN_OUTPUT/pbpipeline/notify_run_complete.touch" ] ; then

        local cc=`wc -w <<<"$CELLS"`
        local ca=`wc -w <<<"$CELLSABORTED"`
        local comment
        if [ $ca -gt 0 ] ; then
            comment=$(( $cc - $ca))" SMRT cells have run. $ca were aborted. Final report will follow soon."
        else
            comment="All $cc SMRT cells have run on the instrument. Final report will follow soon."
        fi
        if rt_runticket_manager --subject processing --reply "$comment" ; then
            touch "$RUN_OUTPUT/pbpipeline/notify_run_complete.touch"
        fi
    fi
}

upload_reports() {
    # Pushes reports to the server, and notifies RT. Does not exit on error so
    # caller should check return code.
    #
    # usage: upload_reports <mode>
    #
    # Where <mode> is NEW, INTERIM or FINAL

    # Caller is responsible for log redirection to plog, but in some cases we want to
    # make a regular log message referencing the plog destination, so this is a bit messy.
    local mode="$1"

    # Get a handle on logging.
    plog </dev/null
    local plog_file="${per_run_log}"

    # Push to server and capture the result.
    # We want stderr from upload_report.sh to go to stdout, so it gets plogged.
    # If the upload fails the report_upload_url.txt it needs to be removed, to distinuguish
    # from the case where there are just no reports.
    rm -f "$RUN_OUTPUT"/pbpipeline/report_upload_url.txt
    if ! upload_report.sh "$RUN_OUTPUT" 2>&1 \
            >"$RUN_OUTPUT"/pbpipeline/report_upload_url.txt  ; then
        log "Upload error. See $plog_file"
        # Maybe notify RT? But this could well be a general network error.
        rm -f "$RUN_OUTPUT"/pbpipeline/report_upload_url.txt
        return 1
    fi

    _fail=0
    if [ "$mode" = NEW ] ; then
        send_summary_to_rt comment "new" "New run. Waiting for cells." || _fail=1
    elif [ "$mode" = FINAL ] ; then
        send_summary_to_rt reply "Finished pipeline" "All processing complete." || _fail=1
    else
        send_summary_to_rt reply "awaiting_cells" "Processing completed for cells $CELLSREADY." || _fail=1
    fi

    # If this fails, the pipeline will continue, since only the final message to RT
    # is seen as critical.
    if [ $_fail != 0 ] ; then
        log "Failed to send summary to RT. See $per_run_log"
        return 1
    fi

    # All was good.
    true
}

send_summary_to_rt() {
    # Sends a summary to RT. It is assumed that "$RUN_OUTPUT"/pbpipeline/report_upload_url.txt is
    # in place and can be read by make_summary.py.
    # All cells on the run will be listed, with a report URL if we have one.
    local reply_or_comment="${1}"
    local run_status="${2:-}"
    local preamble="${3:-A separate report will be produced per cell.}"

    # This was a problem before BASH 4.4 but now we should be fine.
    # https://stackoverflow.com/questions/7577052/bash-empty-array-expansion-with-set-u
    if [ -n "$run_status" ] ; then
        run_status=(--subject "$run_status")
    else
        run_status=()
    fi

    echo "Sending new summary of cells on this PacBio run to RT."
    # Subshell needed to capture STDERR from make_summary.py
    # TODO - test that this works as advertised with different results from make_summary.py
    ( rt_runticket_manager "${run_status[@]}" --"${reply_or_comment}" \
        @<(echo "$preamble" ; echo ;
           make_summary.py --runid "$RUNID" --replinks "$RUN_OUTPUT/pbpipeline/report_upload_url.txt"  --txt - \
           || echo "Error while summarizing run contents." ) ) 2>&1
}

pipeline_fail() {
    # Record a failure of the pipeline. The failure may be due to network outage so try
    # to report to RT but be prepared for that to fail too.

    local stage=${1:-Pipeline}
    local failure

    if [ -z "${2:-}" ] ; then
        # General failure

        # Mark the failure status
        echo "$stage on `date`" > "$RUN_OUTPUT"/pbpipeline/failed

        failure="$stage failed"
    else
        # Failure of a cell or cells
        for c in $2 ; do
            echo "$stage on `date`" > "$RUN_OUTPUT"/pbpipeline/$c.failed
        done

        failure="$stage failed for cells [$2]"
    fi

    # Send an alert to RT.
    # Note that after calling 'plog' we can query '$per_run_log' since all shell vars are global.
    plog "Attempting to notify error to RT"
    br=$'\n'
    if rt_runticket_manager --subject failed --reply "$failure.${br}See log in $per_run_log" |& plog ; then
        log "FAIL $failure on $RUNID. See $per_run_log"
    else
        # RT failure. Complain to STDERR in the hope this will generate an alert mail via CRON
        msg="FAIL $failure on $RUNID, and also failed to report the error via RT. See $per_run_log"
        echo "$msg" >&2
        log "$msg"
    fi
}

get_run_status() { # run_dir
  # invoke pb_run_status.py on $1 and collect some meta-information about the run.
  # We're passing this info to the state functions via global variables.
  local run="$1"

  # This construct allows error output to be seen in the log.
  local rs="$(pb_run_status.py "$run")" || pb_run_status.py "$run" | log 2>&1

  # Capture the various parts into variables (see test/grs.sh in Hesiod)
  local v line
  for v in RUNID/RunID INSTRUMENT/Instrument STATUS/PipelineStatus \
           CELLS/Cells CELLSREADY/CellsReady CELLSPROCESSING/CellsProcessing CELLSDONE/CellsDone \
           CELLSABORTED/CellsAborted ; do
    line="$(awk -v FS=":" -v f="${v#*/}" '$1==f {gsub(/^[^:]*:[[:space:]]*/,"");print}' <<<"$rs")"
    eval "${v%/*}"='"$line"'
  done

  if [ -z "${STATUS:-}" ] ; then
    STATUS=unknown
  fi

  # Resolve output location (this has to work for new runs so we can't follow the symlink)
  RUN_OUTPUT="$TO_LOCATION/$RUNID"
}

###--->>> SCANNING LOOP <<<---###

log "Looking for run directories in $FROM_LOCATION matching (${RUN_NAME_REGEX[@]})"
log "Output will be created in $TO_LOCATION/"

# Generate a list of prefixes from $RUN_NAME_REGEX and store the list
# to PREFIX_RUN_NAME_REGEX for use in the search logic.
for rnregex in "${RUN_NAME_REGEX[@]}" ; do
    # Loop through prefixes up to the first / seen, for which
    # we can use a regex on the regex (or maybe dirname?).
    while [[ "$rnregex" =~ (.+)/(.+) ]] ; do
        rnregex="${BASH_REMATCH[1]}"
        PREFIX_RUN_NAME_REGEX+=("$rnregex")
    done
done
# debug "PREFIX_RUN_NAME_REGEX is (${PREFIX_RUN_NAME_REGEX[@]})"

# 6) Scan through each run until we find something that needs dealing with.
pushd "$FROM_LOCATION" >/dev/null
candidate_run_list=(*/)

while [[ "${#candidate_run_list[@]}" > 0 ]] ; do

  # Shift the first item off the list
  run_basename="${candidate_run_list[0]%/}"
  run_dir="$FROM_LOCATION/$run_basename"
  candidate_run_list=("${candidate_run_list[@]:1}")

  # Scan for full matches, indicating we have a run
  match_found=0
  for rnregex in "${RUN_NAME_REGEX[@]}" ; do
    if [[ "$run_basename" =~ ^${rnregex}$ ]] ; then
      match_found=$(( $match_found + 1 ))
    fi
  done

  if [[ $match_found = 0 ]] ; then
    for prnregex in "${PREFIX_RUN_NAME_REGEX[@]}" ; do
      if [[ "$run_basename" =~ ^${prnregex}$ ]] ; then
        # Add the directory contents to the front of the candidate list for consideration,
        # then continue the main loop.
        candidate_run_list=("$run_basename"/*/ "${candidate_run_list[@]}")
        continue 2
      fi
    done

    # Failing all that, we can prune this directory from further searching
    debug "Ignoring $run_basename"
    continue
  fi

  # invoke runinfo and collect some meta-information about the run. We're passing this info
  # to the state functions via global variables. RUNID INSTRUMENT CELLS etc.
  get_run_status "$run_dir"

  _log=log
  for s in complete aborted testrun ; do
    if [ "$STATUS" = "$s" ] ; then _log=debug ; fi
  done
  $_log "$run_dir has $RUNID from $INSTRUMENT with cell(s) [$CELLS] and status=$STATUS"

  #Call the appropriate function in the appropriate directory.
  BREAK=0
  pushd "$run_dir" >/dev/null ; eval action_"$STATUS"

  # Even though 'set -e' is in effect this next line is reachable if the called function turns
  # it off...
  [ $? = 0 ] || log "Error while trying to run action_$STATUS on $run_basename"
  # So in case this setting got clobbered...
  set -e
  popd >/dev/null

  # If the driver started some actual work it should request to break, as the CRON will start
  # a new scan at regular intervals in any case. We don't want an instance of the driver to
  # spend 2 hours processing then start working on a new run. On the other hand, we don't
  # want a problem run to gum up the pipeline if every instance of the script tries to process
  # it, fails, and then exits.
  # Negated test is needed to play nicely with 'set -e'
  ! [ "$BREAK" = 1 ] || break
done
wait
