#!/bin/bash
set -euo pipefail
shopt -s nullglob

# A script that, given a Sequel run directory, says if it contains an auto-test
# pseudo-run. Return values are:
# 0 - this is a test run
# 1 - this is not a test run
# 2 - not sure (and an error will be printed)

# This check should not be run by the driver until the .transferdone file for the first cell is
# detected, or else it may give a false negative.

if [ -n "${1:-}" ] ; then
    cd "$1"
fi

if [ -e ".not_a_testrun" ] ; then
    # If for some reason we want to force the pipeline to process a test run
    exit 1
fi

cells="$(printf "%s" ?_???/)"

if [ -z "$cells" ] ; then
    # Is this even a run??
    echo "No cells seen in $(pwd)" >&2
    exit 2
elif [ "$cells" != "1_A01/" ] ; then
    # If there is more than one cell it's not a test run
    exit 1
fi

# Annoyingly "test -f" returns 0 ?!
runmeta="$(printf "%s" 1_A01/.*.run.metadata.xml)"
if [ -z "$runmeta" ] ; then
    # Did we wait for .transferdone and friends to appear?
    echo "No .run.metadata.xml in $(pwd)/1_A01" >&2
    exit 2
elif [ ! -f "$runmeta" ] ; then
    echo "$runmeta is not a file"
    exit 2
fi

# This seems a simple check. No need to parse the XML. Just grep.
grep -qF 'InstrumentId="Inst1234"' "$runmeta"
