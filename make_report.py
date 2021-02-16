#!/usr/bin/env python3
import os, sys, re
import logging as L
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
from pprint import pformat
from datetime import datetime
from collections import OrderedDict, namedtuple
import yaml
import base64

def glob():
    """Regular glob() is useful but it can be improved like so.
    """
    from glob import glob
    return lambda p: sorted( (f.rstrip('/') for f in glob(os.path.expanduser(p))) )
glob = glob()

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

        all_info[yaml_info['cell_id']] = yaml_info

    # Glean some pipeline metadata
    if args.pbpipeline:
        pipedata = get_pipeline_metadata(args.pbpipeline)
    else:
        pipedata = dict()

    # And some more of that
    status_info = load_status_info(args.status, fudge=args.fudge_status)

    rep = format_report(all_info,
                        pipedata = pipedata,
                        run_status = status_info,
                        aborted_list = status_info.get('CellsAborted'))

    if (not args.out) or (args.out == '-'):
        print(*rep, sep="\n")
    else:
        L.info("Writing to {}.".format(args.out))
        with open(args.out, "w") as ofh:
            print(*rep, sep="\n", file=ofh)

def escape(in_txt, backwhack=re.compile(r'([][\`*_{}()#+-.!])')):
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
    rundir = os.path.basename( os.path.realpath(pipe_dir + '/..') )

    return dict( version = '+'.join(sorted(versions)),
                 rundir = rundir )

def format_report(all_info, pipedata, run_status, aborted_list=None):
    """ Make a full report based upon the contents of a dict of {cell_id: {infos}, ...}
        Return a list of lines to be printed as a PanDoc markdown doc.
    """
    # Add title and author (ie. this pipeline) and date at the top of the report
    replines = []
    replines.append( "% PacBio run {}".format(pipedata.get('rundir')) )
    replines.append( "% SMRTino version {}".format(pipedata.get('version')) )
    replines.append( "% {}".format(datetime.now().strftime("%A, %d %b %Y %H:%M")) )

    # Add the meta-data
    if run_status:
        replines.append("\n# About this run\n")
        replines.append('\n<dl class="dl-horizontal">')
        for k, v in run_status.items():
            if not(k.startswith('_')) and (k != 'CellsReady'):
                replines.append("<dt>{}</dt>".format(k))
                replines.append("<dd>{}</dd>".format(escape(v)))
        replines.append('</dl>')

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

def embed_image(filename):
    """ Convert an image into base64 suitable for embedding in HTML (and/or PanDoc).
    """
    # FIXME - delete this unused function.
    with open(filename, 'rb') as fh:
        img_as_b64 = base64.b64encode(fh.read()).decode()
    return "<img src='data:image/png;base64,{}'>".format(img_as_b64)

def format_cell(cdict):
    """ Format the cell infos as some sort of PanDoc output
    """
    res = [':::::: {.bs-callout}']

    res.append('<dl class="dl-horizontal">')
    for k, v in sorted(cdict.items()):
        if not(k.startswith('_')):
            res.append("<dt>{}</dt>".format(k))
            res.append("<dd>{}</dd>".format(escape(v)))
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
    res.append('|' + '|'.join(escape(h) for h in headings)  + '|')
    res.append('|' + '|'.join(('-' * len(h)) for h in headings)  + '|')
    for r in rows:
        res.append('|' + '|'.join(fmt(r.get(h)) for h in headings)  + '|')

    return res

def parse_args(*args):
    description = """ Makes a report (in PanDoc format) for a run, by compiling the info from the
                      YAML files and also any extra info discovered.
                  """
    argparser = ArgumentParser( description=description,
                                formatter_class = ArgumentDefaultsHelpFormatter )
    argparser.add_argument("yamls", nargs='*',
                            help="Supply a list of info.yml files to compile into a report.")
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
