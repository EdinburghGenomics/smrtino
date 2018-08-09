#!/usr/bin/env python3
import os, sys, re
import logging as L
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
from pprint import pformat
from datetime import datetime
import yaml

""" Makes a report (in PanDoc format) for a run. We can only report on
    processed SMRT cells where the info.yml has been generated.
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

    if args.pbpipeline:
        pipedata = get_pipeline_metadata(args.pbpipeline)
    else:
        pipedata = dict()

    rep = format_report(all_info, pipedata)

    if (not args.out) or (args.out == '-'):
        print(*rep, sep="\n")
    else:
        L.info("Writing to {}.".format(args.out))
        with open(args.out, "w") as ofh:
            print(*rep, sep="\n", file=ofh)

def get_pipeline_metadata(pipe_dir):
    """ Read the files in the pbpipeline directory to find out some stuff about the
        pipleine.
    """
    # The start_times file reveals the versions applied
    versions = set()
    try:
        with open(pipe_dir + '/start_times') as fh:
            for l in fh:
                versions.add(l.split('@')[0])
    except Exception:
        # Meh.
        pass

    # Plus there's the current version
    try:
        with open(os.path.dirname(__file__) + '/version.txt') as fh:
            versions.add(fh.read().strip())
    except Exception:
        versions.add('unknown')

    # Get the name of the directory what pipe_dir is in
    rundir = os.path.basename( os.path.realpath(pipe_dir + '/..') )

    return dict( version = '+'.join(sorted(versions)),
                 rundir = rundir )

def format_report(all_info, pipedata):
    """ Make a full report based upon the contents of a dict of {cell_id: {infos}, ...}
        Return a list of lines to be printed as a PanDoc markdown doc.
    """
    # Add title and author (ie. this pipeline) and date at the top of the report
    replines = []
    replines.append( "% PacBio run {}".format(pipedata.get('rundir')) )
    replines.append( "% SMRTino version {}".format(pipedata.get('version')) )
    replines.append( "% {}".format(datetime.now().strftime("%A, %d %b %Y %H:%M")) )

    replines.append("\n# My lovely report\n")

    if not all_info:
        replines.append("No SMRT Cells have been processed for this run yet.")

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
    argparser.add_argument("yamls", nargs='*',
                            help="Supply a list of info.yml files to compile into a report.")
    argparser.add_argument("-p", "--pbpipeline", default="pbpipe_from/pbpipeline",
                            help="Directory to scan for pipeline meta-data.")
    argparser.add_argument("-o", "--out",
                            help="Where to save the report. Defaults to stdout.")
    argparser.add_argument("-d", "--debug", action="store_true",
                            help="Print more verbose debugging messages.")

    return argparser.parse_args(*args)

if __name__ == "__main__":
    main(parse_args())
