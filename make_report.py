#!/usr/bin/env python3
import os, sys, re
import logging as L
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
from pprint import pformat
from datetime import datetime
from collections import OrderedDict, defaultdict
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

        # Add in the cstats. This requires some custom parsing of the CSV
        y_base = re.sub(r'\.info\.yml$', '', y)
        yaml_info['_cstats'] = find_cstats(y_base, yaml_info.get('filter_added'))

        all_info[yaml_info['cell_id']] = yaml_info

    # Glean some pipleine metadata
    if args.pbpipeline:
        pipedata = get_pipeline_metadata(args.pbpipeline)
    else:
        pipedata = dict()

    # See if there are any plots to include
    plots = find_sequalstats_plots(args.plots, pipedata.get('rundir'))

    # And some more of that
    status_info = load_status_info(args.status)

    rep = format_report(all_info,
                        pipedata = pipedata,
                        run_status = status_info,
                        aborted_list = status_info.get('CellsAborted'),
                        plots = plots)

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

def find_sequalstats_plots(graph_dir, run_name=None):
    """ Look for all the PNG images. These are drawn per-run so don't apply to
        a specific SMRT cell.
        If run_name is supplied the script will sanity-check all images belong to the run.
    """
    plots_order = """
        Seq run yield and efficiency
        Estimated lib size distribution
        Estimated lib size distribution full data
        Polymerase and subread length profiles
    """

    # Pre-load the dict to get the order I want
    res = OrderedDict( (pn.strip(), None) for pn in plots_order.split("\n") if pn.strip() )

    plots_seen = glob(graph_dir + '/*.*.png')

    for p in plots_seen:
        # Chop off run name and .png extension
        rname = p.split('.')[0]
        fn_bits = p.split('.')[1:-1]

        # These should match
        if run_name and (run_name == rname):
            L.warning("Unexpected PNG file with run_name {} instead of {}.".format(
                                                rname,              run_name))
            continue

        # Now munge the name
        munged_name = re.sub('_', ' ', '_'.join(fn_bits))
        munged_name = munged_name[0].upper() + munged_name[1:]

        res[munged_name] = p

    # Remove missing
    for pn in list(res):
        if not res[pn]: del res[pn]

    return res

def get_plot_annotations():
    """ Returns a dict of information blurbs to be added per plot.
        Or rather, a defaultdict that makes empty dicts.
    """
    res = defaultdict(dict)
    try:
        with open(os.path.dirname(__file__) + '/sequelstats_infos.yml') as yfh:
            res.update( { i['plot'] : dict(msg=i['msg'], hide=bool(i.get('hide')))
                          for i in yaml.safe_load(yfh) } )

    except Exception:
        L.exception("Failed to load the annotations for the plots.")

    return res

def load_status_info(sfile):
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
    return res

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

def format_report(all_info, pipedata, run_status, aborted_list=None, plots=None):
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
            if not(k.startswith('_')):
                replines.append("<dt>{}</dt>".format(k))
                replines.append("<dd>{}</dd>".format(escape(v)))
        replines.append('</dl>')

    if not all_info:
        replines.append("**No SMRT Cells have been processed for this run yet.**")

    # All the cells.
    if all_info:
        replines.append("\n# SMRT Cells\n".format(k))
    for k, v in sorted(all_info.items()):
        replines.append("\n## {}\n".format(k))
        replines.extend(format_cell(v))

    # And the plots
    if plots is not None:
        replines.append("\n# SEQUELstats plots\n")

        # Try to load the descriptions of the plots
        plot_notes = get_plot_annotations()

        if not plots:
            replines.append("**No plots were produced for this run.**")
        else:
            for p, img in plots.items():
                if plot_notes[p].get('hide'):
                    continue

                replines.append("\n## {}\n".format(p))
                replines.append("")
                if plot_notes[p].get('msg'):
                    replines.append("  " + plot_notes[p]['msg'] + "\n")
                replines.append(embed_image(img))

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

def embed_image(filename):
    """ Convert an image into base64 suitable for embedding in HTML (and/or PanDoc).
        I could mess around with thumbnails and lightboxes here but I think showing all
        graphs full size is fine.
    """
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
    argparser.add_argument("-p", "--pbpipeline", default="pbpipeline",
                            help="Directory to scan for pipeline meta-data.")
    argparser.add_argument("--plots", default="sequelstats_plots",
                            help="Directory to scan for PNG plots.")
    argparser.add_argument("-s", "--status", default=None,
                            help="File containing status info on this run.")
    argparser.add_argument("-o", "--out",
                            help="Where to save the report. Defaults to stdout.")
    argparser.add_argument("-d", "--debug", action="store_true",
                            help="Print more verbose debugging messages.")

    return argparser.parse_args(*args)

if __name__ == "__main__":
    main(parse_args())
