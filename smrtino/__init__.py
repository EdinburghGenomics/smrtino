#!/usr/bin/env python3
import os, re
import yamlloader

# Currently provides the "glob" function and the "smrtino_version" constant.
from glob import glob as _glob

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

# YAML convenience functions that use the ordered loader/saver
# yamlloader is basically the same as my yaml_ordered hack. It will go away with Py3.7.
def load_yaml(filename):
    """Load YAML from a file (not a file handle).
    """
    with open(filename) as yfh:
        return yaml.load(yfh, Loader=yamlloader.ordereddict.CSafeLoader)

def dump_yaml(foo, filename=None):
    """Return YAML string and optionally dump to a file (not a file handle)."""
    ydoc = yaml.dump(foo, Dumper=yamlloader.ordereddict.CSafeDumper, default_flow_style=False)
    if filename:
        with open(filename, 'w') as yfh:
            print(ydoc, file=yfh, end='')
    return ydoc

smrtino_version = _determine_version()
