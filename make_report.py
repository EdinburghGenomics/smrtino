#!/usr/bin/env python3
import os, sys, re
import logging as L
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
from pprint import pformat
from datetime import datetime
import yaml

""" Makes a report (in PanDoc format) for a run. We will only report on
    processed SMRT cells where the info.yml has been generated - so no
    reading the XML directly.
    Associated files like the CSV stats will be loaded if found (maybe I
    should link these in the YAML?)
    Run metadata can also be obtained from the pbpipeline directory.
"""

def main(args):

    L.basicConfig(level=(L.DEBUG if args.debug else L.WARNING))

    all_info = dict()
    # Basic basic basic
    for y in args.yamls:

        with open(y) as yfh:
            yaml_info = yaml.safe_load(yfh)

            # Sort by cell ID - all YAML must have this.
            assert yaml_info.get('cell_id'), "All yamls must have a cell ID"

        # Add in the cstats. This requires some custom parsing of the CSV
        y_base = re.sub(r'\.info\.yml$', '', y)
        yaml_info['_cstats'] = find_cstats(y_base, yaml_info.get('filter_added'))

        all_info[yaml_info['cell_id']] = yaml_info

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

def find_cstats(filebase, filt=None):
    """ Given the base name of an .info.yml file, find the related .scraps.cstats.csv
        and .subreads.cstats.csv and load the contents.
        I could give the names of these explicitly in the YAML but it seems over-fiddly.
    """
    res = dict( headers = None,
                data = [] )

    if filt:
        filebase += "." + filt

    # Let's have those stats. I'm only expecting one line in this file, aside from
    # the header.
    try:
        with open(filebase + '.subreads.cstats.csv') as cfh:
            res['headers'] = next(cfh).rstrip().split(',')
            res['data'].append(next(cfh).rstrip().split(','))
            res['data'][-1][0] = "Subreads"
    except FileNotFoundError:
        pass

    # And the second one. I could do this with a loop if there were several files.
    try:
        with open(filebase + '.scraps.cstats.csv') as cfh:
            h = next(cfh).rstrip().split(',')
            if res['headers']:
                assert res['headers'] == h
            else:
                res['headers'] = h
            res['data'].append(next(cfh).rstrip().split(','))
            res['data'][-1][0] = "Scraps"
    except FileNotFoundError:
        pass

    if res['headers']:
        res['headers'][0] = "File"
        return res
    else:
        return None

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

    if not all_info:
        replines.append("**No SMRT Cells have been processed for this run yet.**")

    for k, v in sorted(all_info.items()):

        replines.append("\n# SMRT Cell {}\n".format(k))

        replines.extend(format_cell(v))

    return replines

def format_cell(cdict):
    """ Format the cell infos as some sort of PanDoc output
    """
    res = [':::::: {.bs-callout}']

    res.append('<dl class="dl-horizontal">')
    for k, v in sorted(cdict.items()):
        if not(k.startswith('_')):
            res.append("<dt>" + k + "</dt>")
            res.append("<dd>" + v + "</dd>")
    res.append('</dl>')

    # Now add the stats table
    if cdict.get('_cstats'):
        res.append('')
        res.extend(make_table(cdict['_cstats']))

    return res + ['::::::\n']

def make_table(tdict):
    """ Yet another PanDoc table formatter oh yeah
    """
    res = []
    res.append('|' + '|'.join(tdict['headers'])  + '|')
    res.append('|' + '|'.join(('-' * len(h)) for h in tdict['headers'])  + '|')
    for d in tdict['data']:
        res.append('|' + '|'.join(d)  + '|')

    return res

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
