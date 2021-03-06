#!/bin/bash
set -euo pipefail

# If you just want to push existing reports to the server, see the RSYNC line below.
# Eg:
#  rsync -drvlOt --rsync-path=bin/rsync_reports all_reports \
#        edgenom1@egcloud.bio.ed.ac.uk:smrtino/$(basename $(pwd))/

# See doc/how_to_display.txt for thoughts on how this should really work.

# See where to get the report from (by default, right here)
cd "${1:-.}"
runname="`basename $PWD`"

function echorun(){
    printf $'%q ' "$@" ; printf '\n'
    "$@"
}

# Confirm we do have all_reports/run_report.html
if [ ! -L all_reports/run_report.html ] || [ ! -e all_reports/run_report.html ] ; then
    echo "No such file all_reports/run_report.html or it is not a link."
    false
fi

# Check where (and if) we want to push reports on the server.
if [ "${REPORT_DESTINATION:-none}" == none ] ; then
    echo "Skipping report upload, as no \$REPORT_DESTINATION is set." >&2
    # This will go into RT in place of a link. It's not an error - you can legitimately
    # switch off uploading for testing etc.
    echo '[upload of report was skipped as no REPORT_DESTINATION was set]'
    exit 0
fi
dest="${REPORT_DESTINATION}"

# Allow overriding of RSYNC command. Needed for the setup on egcloud.
# Any required SSH settings should go in ~/.ssh/config
RSYNC_CMD="echorun ${RSYNC_CMD:-rsync}"

echo "Uploading report for $runname to $dest..." >&2
$RSYNC_CMD -drvlOt all_reports $dest/$runname/ >&2
$RSYNC_CMD -drvLOt all_reports/img $dest/$runname/all_reports/ >&2

# Add the index. We now have to make this a PHP script but at least the content is totally fixed.
# This is very similar to what we have on Illuminatus (but not quite).
index_php="$(dirname $BASH_SOURCE)/templates/index.php"
if $RSYNC_CMD -vp "$index_php" $dest/$runname/ >&2 ; then
    echo "...done. Report uploaded and index.php written to ${dest#*:}/$runname/." >&2
else
    echo "...done. Report uploaded but failed to write index.php to ${dest#*:}/$runname/." >&2
fi

# Say where to find it:
# eg. https://egcloud.bio.ed.ac.uk/smrtino/...
echo "Link to report is: ${REPORT_LINK:-$REPORT_DESTINATION}/$runname" >&2
echo "${REPORT_LINK:-$REPORT_DESTINATION}/$runname"
