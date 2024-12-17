#!/bin/bash
set -euo pipefail

## The easiest way to restart a SMRTino run from scratch is to simply remove or rename
## the whole directory. The problem is that if you made config changes/overrides in
## pbpipeline then you would need to wait for the initial pickup of the run and then
## you would need to quickly put the changes back before the full pipeline pass 5
## minutes later (or however the cron is set).
## This script will clean out a run while keeping pbpipeline intact.

function log(){ echo "$@" >&2 ; }

# 1) Ensure we are in a SMRTino output directory

log $'Running pb_run_status.py on current directory \n'"  $(pwd -P) ..."

bin_dir="$(dirname "$BASH_SOURCE")/.."
pstatus="$("$bin_dir"/pb_run_status.py . | grep ^PipelineStatus: | awk '{print $2}')"

if [[ "$pstatus" != failed && "$pstatus" != complete ]] ; then
    log "Run status is $pstatus. Will not proceed."
elif [[ ! -e pipeline.log ]] ; then
    log "pipeline.log is missing. Will not proceed."
else
    log "Looks OK with status '$pstatus'. Ready to clean up."
fi

old_dir="$(mktemp -u old_run_XXXX)"
old_extn="$(awk -F _ '{print $NF}' <<<"$old_dir")"

log
log "Run the following commands:"
log

printf 'mkdir %q\n' "$old_dir"
for f in * ; do
    if [[ "$f" == pbpipeline ]] ; then
        true # leave it (see below)
    elif [[ "$f" =~ ^sc_data\. ]] ; then
        true # skip it
    elif [[ "$f" == snakemake_profile ]] ; then
        true # skip this too
    elif [[ "$f" == slurm_output ]] ; then
        true # skip this too
    elif [[ "$f" == pipeline.log ]] ; then
        printf 'mv %q %q\n' "$f" "$f.old.$old_extn"
    else
        printf 'mv -t %q/ %q\n' "$old_dir" "$f"
    fi
done

# Finally clean out pbpipeline ro reset the run
printf 'rm -vf pbpipeline/*.started pbpipeline/*.done\n'
printf 'rm -vf pbpipeline/failed pbpipeline/*.failed\n'
