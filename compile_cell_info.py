#!/usr/bin/env python3
import os, sys
import logging as L
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter

from smrtino import load_yaml, dump_yaml

""" The info needed to report on a SMRT cell consists of several YAML files:
        sc_data.yaml about the files in the upstream
        unassigned.yaml about the unassigned reads (even with no barcode in use!)
        bc1.ymal bc2.yaml about the barcodes.

    This super-simple script just outputs a file linking to these other files.
"""

def main(args):

    L.basicConfig(level=(L.DEBUG if args.debug else L.WARNING), stream=sys.stderr)

    info = gen_info(args)

    if args.extract_ids:
        info.update(extract_ids(args.bcfiles[0]))

    dump_yaml(info, fh=sys.stdout)

def extract_ids(yaml_file):
    """Pull some bits needed for link_to_smrtlink.py
    """

    ydata = load_yaml(yaml_file)

    return { k: ydata[k]
             for k in "run_id run_slot cell_id cell_uuid".split() }

def gen_info(args):

    res = dict()
    for x in ['sc_data', 'unassigned']:
        if getattr(args, x):
            res[x] = check_exists(getattr(args, x), args.check_exists)

    res['barcodes'] = [ check_exists(f, args.check_exists) for f in args.bcfiles ]

    return res

def check_exists(f, really_check=True):
    """Check that a file exists. In fact, check it's valid YAML
    """
    if really_check:
        load_yaml(f)

    return '@' + f

def parse_args(*args):
    description = """Provide XML for the various bits of report.
                  """
    argparser = ArgumentParser( description=description,
                                formatter_class = ArgumentDefaultsHelpFormatter )
    argparser.add_argument("bcfiles", nargs='*',
                            help="Info YAML files to be linked per barcode")
    argparser.add_argument("--sc_data",
                            help="Location of sc_data.yaml for the cell")
    argparser.add_argument("--unassigned",
                            help="Location of info.yaml for unassigned reads")
    argparser.add_argument("-d", "--debug", action="store_true",
                            help="Print more verbose debugging messages.")
    argparser.add_argument("-c", "--check_exists", action="store_true",
                            help="Check that the files exist.")
    argparser.add_argument("-x", "--extract_ids", action="store_true",
                            help="Add the run_id, cell_id, cell_uuid from the first info file")

    return argparser.parse_args(*args)


if __name__ == "__main__":
    main(parse_args())
