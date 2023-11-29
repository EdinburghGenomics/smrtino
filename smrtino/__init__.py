#!/usr/bin/env python3
import os, re
from datetime import datetime

# Currently provides the "glob" function and the "smrtino_version" constant.
from glob import glob as _glob

# And some YAML enhancement
from smrtino.yaml_ordered import yaml, yamlloader, dictify
from smrtino.aggregator import aggregator

def glob(pattern):
    """Improves on the regular glob function by supporting tilde expansion,
       sorting the result, and stripping off '/' if you end the pattern with '/'
       in order to only match directories.
    """
    return sorted( (f.rstrip('/') for f in _glob(os.path.expanduser(pattern))) )

def _determine_version():
    """Report the version of SMRTino being used. Normally this is in version.txt
       but we can factor in GIT commits in the dev environment.
       This logic is copied from Hesiod.
       Note that uncommitted code cannot easily be detected, so I don't try.
    """
    try:
        with open(os.path.dirname(__file__) + '/../version.txt') as fh:
            vers = fh.read().strip()
    except OSError:
        return 'unknown'

    # Inspired by MultiQC, if there is a .git dir then dig into it
    try:
        with open(os.path.dirname(__file__) + '/../.git/HEAD') as fh:
            git_head = fh.read().strip()

        if git_head.startswith('ref:'):
            # We're at a branch tip
            git_branch = git_head[5:]
            git_branch_name = git_branch.split('/')[-1]

            # Load the actual commit ID
            with open(os.path.dirname(__file__) + '/../.git/' + git_branch) as fh:
                git_head = fh.read().strip()
        else:
            git_branch_name = 'none'

        # Having done all that, see if git_head matches the tag that matches vers
        with open(os.path.dirname(__file__) + '/../.git/refs/tags/v' + vers) as fh:
            git_version_commit = fh.read().strip()

        if git_version_commit != git_head:
            # No it doesn't. So add some extra info to the version.
            vers = "{}-{}-{}".format(vers, git_branch_name, git_head[:8])

    except OSError:
        # We're not getting anything useful from .git
        pass

    return vers

def parse_run_name(name):
    """Parse a run name like r64175e_20230811_115046/ and see what it tells us.
       You can also parse a cell name if you like.
    """
    # Tolerate extra slashes
    name = name.strip('/')

    res = dict( run_or_cell = "",
                fullname = name,
                platform = "unknown",
                instrument = "unknown",
                rundate = None )

    # We expect to see a pattern like this
    mo = re.fullmatch(r"([rm])(\d{5})(e?)_(\d+_\d+)(_s\d)?", name)

    if not mo:
        # Ooopsie. Caller should check they got a real result!
        return res

    res['run_or_cell'] = { 'r' : "run",
                           'm' : "cell" }.get(mo.group(1), "neither")
    res['platform'] = { '5'  : "Sequel I",
                        '6'  : "Sequel II",
                        '6e' : "Sequel IIe",
                        '8'  : "Revio" }.get( mo.group(2)[0] + mo.group(3), "unknown" )
    res['instrument'] = mo.group(2) + mo.group(3)
    # The numbers give us a date and time so let's parse it
    # But the format for cells and runs is different!
    try:
        if len(mo.group(4)) == 15:
            res['rundate'] = datetime.strptime(mo.group(4), "%Y%m%d_%H%M%S")
        elif len(mo.group(4)) == 13:
            res['rundate'] = datetime.strptime(mo.group(4), "%y%m%d_%H%M%S")
    except ValueError:
        # Invalid date? Really?
        pass

    # Revio cells hava slot number too
    if mo.group(5):
        res['slot'] = mo.group(5).strip("_")

    return res

# YAML convenience functions that use the ordered loader/saver
# yamlloader is basically the same as my yaml_ordered hack. It will go away with Py3.7.
def load_yaml(filename, dictify_result=False):
    """Load YAML from a file (not a file handle).
    """
    with open(filename) as yfh:
        y = yaml.ordered_load(yfh)

        return dictify(y) if dictify_result else y

def dump_yaml(foo, filename=None, fh=None):
    """Return YAML string and optionally dump to a file (or a file handle)."""
    ydoc = yaml.safe_dump(foo, default_flow_style=False)
    if fh:
        print(ydoc, file=fh, end='')
    if filename:
        with open(filename, 'w') as yfh:
            print(ydoc, file=yfh, end='')
    return ydoc

smrtino_version = _determine_version()
