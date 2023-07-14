#!/bin/bash
set -euo pipefail

# Script to be run on egcloud to clean up the test run reports from the list.
# I can run this now and run it later if needed.
# SMRTino2 shoul not produce these reports at all, and should never open
# (or else should auto-close) the helpdesk tickets.

cd /mnt/datastore_reports/smrtino/

mkdir -p auto_test_runs

# Rely on a simple grep for "Inst1234" which is characteristic of auto-tests.
for r in $( grep -l Inst1234 r64175e_*/all_reports/*.pan | cut -d/ -f1 | uniq ) ; do
    mv -vt auto_test_runs "$r"
done

