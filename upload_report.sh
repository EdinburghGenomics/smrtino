#!/bin/bash
set -euo pipefail

# If you just want to push existing reports to the server, see the RSYNC line below.
# Eg:
#  rsync -drvlOt --rsync-path=bin/rsync_reports all_reports \
#        edgenom1@egcloud.bio.ed.ac.uk:smrtino/$(basename $(pwd))/

# See doc/how_to_display.txt for thoughts on how this should really work.

# See where to get the report from (by default, right here)
cd "${1:-.}"
runname="$(basename "$PWD")"

function echorun(){
    printf '%q ' "$@" ; printf '\n'
    "$@"
}

# If we have no HTML report (yet) this is now OK
if ! compgen -G "all_reports/*.html" >/dev/null ; then
    echo 'No HTML files found in ./all_reports' >&2
    exit 0
fi

# Check where (and if) we want to push reports on the server.
if [ "${REPORT_DESTINATION:-none}" == none ] ; then
    echo "Skipping report upload, as no \$REPORT_DESTINATION is set." >&2
    # Leave the output empty. It's not an error - you can legitimately
    # switch off uploading for testing etc.
    exit 0
fi
dest="${REPORT_DESTINATION}"

# Allow overriding of RSYNC command. Needed for the setup on egcloud.
# Any required SSH settings should go in ~/.ssh/config
RSYNC_CMD="echorun ${RSYNC_CMD:-rsync}"

echo "Uploading reports for $runname to $dest..." >&2
$RSYNC_CMD -drvlOt all_reports/ $dest/$runname/ >&2
$RSYNC_CMD -drvLOt all_reports/img $dest/$runname/ >&2

# I think we no longer need the index.php
# Output one line per report.
# eg. https://egcloud.bio.ed.ac.uk/smrtino/...
echo "Link to reports is: ${REPORT_LINK:-$REPORT_DESTINATION}/$runname" >&2
for htmlrep in all_reports/*.html ; do
    echo "${REPORT_LINK:-$REPORT_DESTINATION}/$runname/$(basename "$htmlrep")"
done
