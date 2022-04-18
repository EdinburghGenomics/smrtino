#!/usr/bin/env python3
import os, sys, re
import logging as L
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
from pprint import pformat
from datetime import datetime
from collections import OrderedDict
import yaml
import base64

from smrtino import glob

""" Makes a report (in PanDoc format) for a run. We will only report on
    processed SMRT cells where the info.yml has been generated - so no
    reading the XML directly.
    Associated files like the CSV stats will be loaded if found (maybe I
    should link these in the YAML?)
    Run metadata can also be obtained from the pbpipeline directory.
"""

def main(args):

    L.basicConfig(level=(L.DEBUG if args.debug else L.WARNING))

    # Collect the infos from the files into keyed-alike dicts.
    all_yamls = dict( info  = dict(),
                      link = dict() )

    for y in args.yamls:

        yaml_type = y.split('.')[-1]
        if yaml_type not in all_yamls:
            exit(f"The file {y} is not something I know hot to process - I know about {set(all_yamls)}")

        with open(y) as yfh:
            yaml_info = yaml.safe_load(yfh)

            # All YAML files have a 'cell_id' or 'cell_dir' which will be a common key
            cell_dir = yaml_info.get('cell_dir', yaml_info.get('cell_id'))
            if not cell_dir:
                exit("All yamls must indlude a cell ID - eg. m54321_200211_123456")

        # Push it into the dict
        if cell_dir in all_yamls[yaml_type]:
            exit(f"Cell {cell_dir} was already in all_yamls[{yaml_type}]. Will not overwrite it.")
        all_yamls[yaml_type][cell_dir] = yaml_info

    # Glean some pipeline metadata
    if args.pbpipeline:
        pipedata = get_pipeline_metadata(args.pbpipeline)
    else:
        pipedata = dict()

    # And some more of that
    status_info = load_status_info(args.status, fudge=args.fudge_status)

    rep = format_report(all_yamls,
                        pipedata = pipedata,
                        run_status = status_info,
                        aborted_list = status_info.get('CellsAborted'))

    if (not args.out) or (args.out == '-'):
        print(*rep, sep="\n")
    else:
        L.info("Writing to {}.".format(args.out))
        with open(args.out, "w") as ofh:
            print(*rep, sep="\n", file=ofh)

def escape_md(in_txt, backwhack=re.compile(r'([][\\`*_{}()#+-.!])')):
    """ HTML escaping is not the same as markdown escaping
    """
    return re.sub(backwhack, r'\\\1', str(in_txt))

def load_status_info(sfile, fudge=None):
    """ Parse the output of pb_run_status.py, either from a file or more likely
        from a BASH <() construct - we don't care.
        It's quasi-YAML format but I'll not use the YAML parser. Also I want to
        preserve the order.
    """
    res = OrderedDict()
    if sfile:
        with open(sfile) as fh:
            for line in fh:
                k, v = line.split(':', 1)
                res[k.strip()] = v.strip()
    if fudge:
        # Note this keeps the order or else adds the status on the end.
        res['PipelineStatus'] = fudge
    return res

def get_pipeline_metadata(pipe_dir):
    """ Read the files in the pbpipeline directory to find out some stuff about the
        pipeline. This is in addition to what we get from pb_run_status.
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

    # Plus there's the current version, which should be in $SMRTINO_VERSION
    try:
        versions.add(os.environ['SMRTINO_VERSION'])
    except KeyError:
        versions.add('unknown')

    # Get the name of the directory what pipe_dir is in
    # Should be the same as the run name.
    rundir = os.path.basename( os.path.realpath(pipe_dir + '/..') )

    return dict( version = '+'.join(sorted(versions)),
                 rundir = rundir )

def format_report(all_yamls, pipedata, run_status, aborted_list=None, rep_time=None):
    """ Make a full report based upon the contents of a dict of {cell_id: {infos}, ...}
        Return a list of lines to be printed as a PanDoc markdown doc.
    """
    time_header = (rep_time or datetime.now()).strftime("%A, %d %b %Y %H:%M")

    # Add title and author (ie. this pipeline) and date at the top of the report
    replines = []
    replines.append( "% PacBio run {}".format(pipedata.get('rundir')) )
    replines.append( "% SMRTino version {}".format(pipedata.get('version')) )
    replines.append( "% {}\n".format(time_header) )

    # Add the meta-data
    if run_status:
        replines.append("\n# About this run\n")
        replines.append('\n<dl class="dl-horizontal">')
        for k, v in run_status.items():
            if not(k.startswith('_')) and (k != 'CellsReady'):
                replines.append("<dt>{}</dt>".format(k))
                replines.append("<dd>{}</dd>".format(escape_md(v)))
        replines.append('</dl>')

    all_info = all_yamls['info']
    if not all_info:
        replines.append("**No SMRT Cells have been processed for this run yet.**")

    # All the cells, including per-cell plots
    if all_info:
        replines.append("\n# SMRT Cells\n")
    for k, v in sorted(all_info.items()):
        replines.append("\n## {}\n".format(k))
        replines.extend(format_cell(v))

    if aborted_list and aborted_list.split():
        # Specifically note incomplete cells
        replines.append("\n# Aborted cells\n")
        replines.append(("{} SMRT cells on this run did not run to completion and will" +
                         " not be processed further.").format(len(aborted_list.split())))
        replines.append("")
        replines.append("    Slots: {}".format(aborted_list))

    # Footer??
    replines.append("\n*~~~*")

    return replines

def blockquote(txt):
    """ Block quote some pandoc text. Returns a list of strings
    """
    return [''] + [ "> " + t for t in txt.split('\n') ] + ['']

def format_cell(cdict):
    """ Format the cell infos as some sort of PanDoc output
    """
    res = [':::::: {.bs-callout}']

    res.append('<dl class="dl-horizontal">')
    for k, v in sorted(cdict.items()):
        if not(k.startswith('_')):
            res.append("<dt>{}</dt>".format(k))
            res.append("<dd>{}</dd>".format(escape_md(v)))
    # If there is no project, we should make this explicit
    if not 'ws_project' in cdict:
        res.append("<dt>{}</dt>".format('ws_project'))
        res.append("<dd><span style='color: Tomato;'>{}</span></dd>".format('None'))
    res.append('</dl>')

    # Now add the stats table for stuff produced by fasta_stats.py
    if cdict.get('_cstats'):
        res.append('')
        res.extend(make_table(cdict['_cstats']))

    # Now add the blob and histo plots. The input data defines the plot order
    # and placement.
    for plot_section in cdict.get('_plots', []):
        for plot_group in plot_section:
            res.append('\n### {}\n'.format(plot_group['title']))

            # plot_group['files'] will be a a list of lists, so plot
            # each list a s a row.
            for plot_row in plot_group['files']:
                res.append("<div class='flex'>")
                res.append(" ".join(
                        "[plot]({}){{.thumbnail}}".format("img/" + p)
                        for p in plot_row
                    ))
                res.append("</div>")

    return res + ['::::::\n']

def make_table(rows):
    """ Yet another PanDoc table formatter oh yeah
    """
    headings = rows[0]['_headings']

    def fmt(v):
        if type(v) == float:
            return "{:,.02f}".format(v)
        elif type(v) == int:
            return "{:,d}".format(v)
        else:
            return "{}".format(v)

    res = []
    res.append('|' + '|'.join(escape_md(h) for h in headings)  + '|')
    res.append('|' + '|'.join(('-' * len(escape_md(h))) for h in headings)  + '|')
    for r in rows:
        res.append('|' + '|'.join(escape_md(fmt(r.get(h))) for h in headings)  + '|')
    res.append('')

    return res

def parse_args(*args):
    description = """ Makes a report (in PanDoc format) for a run, by compiling the info from the
                      YAML files and also any extra info discovered.
                  """
    argparser = ArgumentParser( description=description,
                                formatter_class = ArgumentDefaultsHelpFormatter )
    argparser.add_argument("yamls", nargs='*',
                            help="Supply a list of info.yml and link.yml files to compile into a report.")
    argparser.add_argument("-p", "--pbpipeline", default="pbpipeline",
                            help="Directory to scan for pipeline meta-data.")
    argparser.add_argument("-s", "--status", default=None,
                            help="File containing status info on this run.")
    argparser.add_argument("-f", "--fudge_status", default=None,
                            help="Override the PipelineStatus shown in the report.")
    argparser.add_argument("-o", "--out",
                            help="Where to save the report. Defaults to stdout.")
    argparser.add_argument("-d", "--debug", action="store_true",
                            help="Print more verbose debugging messages.")

    return argparser.parse_args(*args)

if __name__ == "__main__":
    main(parse_args())
