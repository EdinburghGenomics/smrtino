#!/usr/bin/env python3

import os, sys
import re

from pprint import pprint

def scanhead(bamfile):
    """Inspect SAM headers to see if the file has binned quality
       scores or not.
    """
    pg_lines = []

    for l in bamfile:
        if not l.startswith("@"):
            break
        if l.startswith("@PG"):
            pg_lines.append(l.rstrip("\n"))

    # Basic parser. Could just use PySAM for this I guess.
    pg_dicts = []
    for pgl in pg_lines:
        mo = re.match(r"(.*)\tCL:(.*)", pgl)
        if mo and 'PN:ccs' in mo.group(1).split("\t"):
            pg_dicts.append(dict(CL = mo.group(2)))

    return check_pg_lines(pg_dicts)

def scanbam(bamfile):
    """Inspect bamfile and see if it has binned quality scores or not.
    """
    import pysam
    with pysam.AlignmentFile(bamfile, "rb",
                             check_sq = False,
                             ignore_truncation = True) as samfh:

        # Only reading the headers should not need the BAM index
        ccs_pg_lines = [ l for l in samfh.header.get('PG', [])
                         if l.get('PN') == 'ccs' ]

    return check_pg_lines(ccs_pg_lines)

def check_pg_lines(pg_lines):
    """The caller has obtained the PG lines from the BAM header wher PN == 'ccs'
       so now here's the common logic to decide if '--binned-qvs' was set.
    """

    if len(pg_lines) != 1:
        return 'unknown'

    # We are looking for the "--binned-qvs=false" string within the command line
    cl = pg_lines[0].get('CL')

    if not cl:
        # Eh?
        return 'unknown'

    if " --binned-qvs=false" in cl:
        return "unbinned"
    else:
        return "binned"

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] == "-":
        print( scanhead(sys.stdin) )

    elif len(sys.argv) == 2 :
        print( scanbam(sys.argv[1]) )

    else:
        exit("Usage: binned_or_not.py <somefile.bam>")


