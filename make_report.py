#!/usr/bin/env python3
import os, sys, re
import logging as L
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
from pprint import pformat
import yaml

""" Makes a report (in PanDoc format) for a run.
"""

def main(args):

    L.basicConfig(level=(L.DEBUG if args.debug else L.WARNING))

    all_info = dict()
    # Basic basic basic
    for y in args.yamls:
        with open(y) as yfh:
            yaml_info = yaml.safe_load(yfh)

            # Sort by cell ID - all YAML must have this.
            assert yaml_info.get('cell'), "All yamls must have a cell ID"

        cstats = re.sub(r'\.info\.yml$', '.cstats.csv', y)
        try:
            with open(cstats) as cfh:
                yaml_info['cstats'] = cfh.read()
        except FileNotFoundError:
            pass

        all_info[yaml_info['cell']] = yaml_info

    rep = format_report(all_info)

    if (not args.out) or (args.out == '-'):
        print(*rep, sep="\n")
    else:
        L.info("Writing to {}.".format(args.out))
        with open(args.out, "w") as ofh:
            print(*rep, sep="\n", file=ofh)

def format_report(all_info):
    """ Make a full report based upon the contents of a dict of {cell_id: {infos}, ...}
        Return a list of lines to be printed as a PanDoc markdown doc.
    """
    replines = ["\n# My lovely report\n"]

    for k, v in sorted(all_info.items()):

        replines.append("\n### SMRT Cell {}\n".format(k))

        replines.append("```")
        replines.append(pformat(v))
        replines.append("```")

    return replines

def parse_args(*args):
    description = """ Makes a report (in PanDoc format) for a run, by compiling the info from the
                      YAML files and also any extra info discovered.
                  """
    argparser = ArgumentParser( description=description,
                                formatter_class = ArgumentDefaultsHelpFormatter )
    argparser.add_argument("yamls", nargs='+',
                            help="Supply a list of info.yml files to compile into a report.")
    argparser.add_argument("-o", "--out",
                            help="Where to save the report. Defaults to stdout.")
    argparser.add_argument("-d", "--debug", action="store_true",
                            help="Print more verbose debugging messages.")

    return argparser.parse_args(*args)

if __name__ == "__main__":
    main(parse_args())
