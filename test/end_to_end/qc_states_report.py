#!/bin/env python3

""" Report status of all runs. Dashboard stylee.
    You can report on the live runs from the devel code:
    env RUN_NAME_REGEX='r54041_2018.*' ENVIRON_SH=./environ.sh.sample qc_states_report.py
"""

# This was a shell script. Re-written in Python as it was getting silly.
import os, sys, re
from collections import defaultdict
from subprocess import run, PIPE
from YAMLOrdered import yaml

# Allow importing of modules from up the way.
PROG_BASE=os.path.dirname(__file__)+'/../..'
sys.path.insert(0,PROG_BASE)

# My souped-up glob
def glob():
    """Regular glob() is useful but it can be improved like so.
    """
    from glob import glob
    return lambda p: sorted( (f.rstrip('/') for f in glob(os.path.expanduser(p))) )
glob = glob()

# Direct import from a runnable program. This should really be made a library.
from pb_run_status import RunStatus

# Default environment
environ = dict( ENVIRON_SH = os.environ.get("ENVIRON_SH", "./environ.sh"),
                RUN_NAME_REGEX = ".*_.*_.*_[^.]*" )

# I need to load environ.sh into my environment, which is a little tricky if
# I want to keep allowing general shell syntax in these files (which I do).
def load_environ():
    #PATH="$(readlink -f "$(dirname $BASH_SOURCE)"/../..):$PATH"
    if os.path.exists(environ['ENVIRON_SH']):
        cpi = run(r'''cd "{}" && source ./"{}" && printenv'''.format(
                         os.path.dirname(environ['ENVIRON_SH']),
                                          os.path.basename(environ['ENVIRON_SH']) ),
                shell = True,
                stdout = PIPE,
                universal_newlines = True)

        environ.update([ l.split('=',1) for l in cpi.stdout.split('\n') if '=' in l ])

def debug(*args):
    """ Poor mans logger
    """
    if environ.get('DEBUG') and environ.get('DEBUG') != '0':
        print(*args)
        return True
    return False

# Behaviour should match what's in driver.sh
def main(args):

    load_environ()

    print("Looking for run directories matching regex {}/{}".format(
                environ['TO_LOCATION'], environ['RUN_NAME_REGEX'] ))
    print("Runs considered stalled after {} hours.".format(environ.get('STALL_TIME')))

    rnr = environ['RUN_NAME_REGEX']
    if not rnr.endswith('$'):
        rnr += '$'
    rnr = re.compile(rnr)

    res = defaultdict(lambda: dict(
            rcount = 0,
            runs = [],
            instruments = defaultdict(int)
        ))
    pversions = dict()

    # Scan all of the directories in quick mode, but only if they match the regex
    for arun in glob(environ['TO_LOCATION'] + '/*/'):

        runid = os.path.basename(arun)

        if not re.match(rnr, runid):
            debug("Ignoring {} - regex mismatch".format(runid))
            continue

        # We just need to know about the instrument and status, which
        # can be done quickly.
        # You can ask the same by running RunStatus.py -q ...
        rs = RunStatus(arun, 'q', stall_time=environ.get('STALL_TIME'))

        # Note I'm overwriting runid - this will prune any .extension
        runid = rs.get_run_id()
        rinstrument = rs.get_instrument()
        rstatus = rs.get_status()

        # Collect the runs by status and instrument counts
        res[rstatus]['rcount'] += 1
        res[rstatus]['runs'].append(runid)
        res[rstatus]['instruments'][rinstrument] += 1

        # If complete, see what version it was done with.
        # Normally, skip this. It's too slow.
        if debug():
            if rstatus == "complete":
                for f in glob(arun + "/pipeline/output/QC/run_info.*.yml"):
                    with open(f) as fh:
                        fdata = yaml.safe_load(fh)
                        for sect in fdata.values():
                            if 'Pipeline Version' in sect:
                                pversions[runid] = fdata['Pipeline Version']
            debug("Run {} completed with pipeline version {}".format(runid, pversions[runid]))

    #End of loop through directories. Now rearrange instruments from a defaultdict to a list and print.
    for resv in res.values():
        resv['instruments'] = [ dict(name=k, count=v) for k, v in sorted(resv['instruments'].items()) ]

    print("### Run report as YAML:")
    print(yaml.safe_dump(res))


if __name__ == '__main__':
    main(sys.argv[1:])
