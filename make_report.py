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

def load_all_inputs(list_of_yamls, yaml_types=("info", "link", "pdf")):
    """Read the provided YAML and PDF files into a dict of dicts.
       The sub-dicts are both keyed on the cell filename.
    """
    all_yamls = { k: dict() for k in yaml_types }

    for y in list_of_yamls:

        # We should probably put the PDF files in a separate dict.
        if y.endswith('.pdf'):
            # Oh it's a PDF not a YAML
            cell_dir = y.split("/")[-1][:-len('.pdf')]
            all_yamls['pdf'][cell_dir] = y
            continue

        yaml_type = y.split('.')[-2]
        if yaml_type not in all_yamls:
            exit(f"The file {y} is not something I know how to process - I know about {yaml_types}")

        with open(y) as yfh:
            yaml_info = yaml.safe_load(yfh)

            # All YAML files have a 'cell_id' or 'cell_dir' which will be a common key
            cell_dir = yaml_info.get('cell_dir', yaml_info.get('cell_id'))
            if not cell_dir:
                exit("All yamls must include a cell ID - eg. m54321_200211_123456")

        # Push it into the dict
        if cell_dir in all_yamls[yaml_type]:
            exit(f"Cell {cell_dir} was already in all_yamls[{yaml_type}]. Will not overwrite it.")
        all_yamls[yaml_type][cell_dir] = yaml_info

    return all_yamls

def rejig_status_info(status_info, fudge=None, smrtlink_qc_link=None, experiment=None, instrument=None):
    """Re-jig the status_info into the format we want to display in the
       'About this run' section.
       This was previously done within format_report() but I broke it out.
    """
    # First eliminate anything that starts with an underscore, and 'CellsReady'
    new_info = OrderedDict([ (k, v) for k, v in status_info.items()
                              if not(k.startswith('_'))
                              and (k != 'CellsReady') ])

    # Now fudge the run status if requested
    if fudge:
        new_info['PipelineStatus'] = fudge

    # And the instrument, once we get a definitive report from the XML
    if instrument:
        new_info['Instrument'] = instrument

    # Now add the smrtlink_qc_link at the top
    if smrtlink_qc_link:
        assert type(smrtlink_qc_link) is tuple
        new_info['SMRTLink Run QC'] = smrtlink_qc_link
        new_info.move_to_end('SMRTLink Run QC', last=False)

    # And the experiment. Also at the top
    if experiment:
        new_info['Experiment'] = experiment
        new_info.move_to_end('Experiment', last=False)

    # And optionally remove CellsAborted if it's blank
    if 'CellsAborted' in new_info:
        if not new_info['CellsAborted']:
            del new_info['CellsAborted']

    return new_info

def main(args):

    L.basicConfig(level=(L.DEBUG if args.debug else L.WARNING))

    all_yamls = load_all_inputs(args.yamls)

    # Glean some pipeline metadata
    if args.pbpipeline:
        pipedata = get_pipeline_metadata(args.pbpipeline)
    else:
        pipedata = dict()

    # And some more of that
    status_info = load_status_info(args.status)

    # Re-jig the status_info into the format we want to display in the
    # "About this run" section.
    run_status = rejig_status_info( status_info,
                                    fudge = args.fudge_status,
                                    smrtlink_qc_link = get_qc_link(all_yamls),
                                    experiment = get_run_metadata(all_yamls, 'ExperimentId'),
                                    instrument = get_run_metadata(all_yamls, 'Instrument') )

    rep = format_report(all_yamls,
                        pipedata = pipedata,
                        run_status = run_status,
                        aborted_list = status_info.get('CellsAborted'))

    if (not args.out) or (args.out == '-'):
        print(*rep, sep="\n")
    else:
        L.info(f"Writing to {args.out}.")
        with open(args.out, "w") as ofh:
            print(*rep, sep="\n", file=ofh)

def get_run_metadata(all_yamls, k):
    """ Get an item from the '_run' section of the 'info' metadata.
        If the key k is not found in any of the dicts we'll return None.

        If there are multiple values (there shouldn't be!) we'll return a printable
        string like "a, b".
    """
    if not all_yamls.get('info'):
        L.warning("No 'info' metadata was loaded.")
        return None

    info_yamls = all_yamls['info'].values()
    run_dicts = filter(None, ( y.get('_run') for y in info_yamls ))
    all_v = set(filter(None, ( r.get(k) for r in run_dicts )))

    if all_v:
        return ", ".join(sorted(all_v))
    else:
        # k was not found at all
        return None

def get_qc_link(all_yamls):
    """ Get the smrtlink_run_uuid and smrtlink_run_link which should be common
        to all the link yaml files
    """
    if not all_yamls.get('link'):
        L.warning("No 'link' metadata was loaded.")
        return None

    link_yamls = all_yamls['link'].values()
    uuid_vals = set(filter(None, ( y.get('smrtlink_run_uuid') for y in link_yamls )))
    link_vals = set(filter(None, ( y.get('smrtlink_run_link') for y in link_yamls )))

    errors = 0
    if len(uuid_vals) != 1:
        L.error(f"Could not get a common Run UUID from {len(link_yamls)} link files")
        errors += 1
    if len(link_vals) != 1:
        L.error(f"Could not get a common Run link from {len(link_yamls)} link files")
        errors += 2

    if errors:
        return None
    else:
        return uuid_vals.pop(), link_vals.pop()

def escape_md(in_txt, backwhack=re.compile(r'([][\\`*_{}()#+-.!<>])')):
    """ HTML escaping is not the same as markdown escaping
    """
    return re.sub(backwhack, r'\\\1', str(in_txt))

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

          * all_yamls should be a dict with 'info' and 'link' sub-dicts
          * pipedata is a dict from get_pipeline_metadata()
          * run_status is a dict from rejig_status_info()
          * aborted_list is a string (nor a list!) listing aborted cells,
          * rep_time is a datetime but normally not needed as the current time will be used
    """
    time_header = (rep_time or datetime.now()).strftime("%A, %d %b %Y %H:%M")

    # Add title and author (ie. this pipeline) and date at the top of the report
    replines = []
    replines.append( f"% PacBio run {pipedata.get('rundir')}" )
    replines.append( f"% SMRTino version {pipedata.get('version')}" )
    replines.append( f"% {time_header}\n" )

    # Add the run_status meta-data
    run_status = run_status or {}
    replines.append("\n# About this run\n")
    replines.append('<dl class="dl-horizontal">')

    # The dict has been pre-processed. Links will be a pair of (uuid, hyperlink)
    for k, v in run_status.items():
        replines.append(f"<dt>{k}</dt>")
        if type(v) is tuple:
            replines.append(f"<dd>[{escape_md(v[0])}]({v[1]})</dd>")
        else:
            replines.append(f"<dd>{escape_md(v)}</dd>")
    replines.append('</dl>\n')

    all_info = all_yamls['info']
    if not all_info:
        replines.append("**No SMRT Cells have been processed for this run yet.**")

    # All the cells, including per-cell plots
    if all_info:
        replines.append("\n# SMRT Cells\n")
    for k, v in sorted(all_info.items()):
        # See if we can link this cell
        cell_link = all_yamls['link'].get(k, {}).get('smrtlink_cell_link')

        replines.append(f"\n## {escape_md(k)}\n")

        # See if we have a PDF and/or link to SMRTLink for this cell
        smrt_links = []
        if all_yamls['pdf'].get(k):
            # \U0001F5BA is a document emoji
            smrt_links.append(f"[\U0001F5BA SMRTLink PDF report]({all_yamls['pdf'][k]}) ")
        if cell_link:
            smrt_links.append(f"[SMRTLink Dataset]({cell_link}) ")
        if smrt_links:
            replines.extend([ "", " \| ".join(smrt_links), "" ])

        replines.extend(format_cell(v, cell_link))

    if aborted_list and aborted_list.split():
        # Specifically note incomplete cells
        replines.append("\n# Aborted cells\n")
        replines.append(f"{len(aborted_list.split())} SMRT cells on this run did not run"
                         " to completion and will not be processed further.")
        replines.append("")
        replines.append(f"    Slots: {aborted_list}")

    # Footer??
    replines.append("\n*~~~*")

    return replines

def blockquote(txt):
    """ Block quote some pandoc text. Returns a list of strings
    """
    return [''] + [ "> " + t for t in txt.split('\n') ] + ['']

def format_cell(cdict, cell_link=None):
    """ Format the cell infos as some sort of PanDoc output
    """
    res = [':::::: {.bs-callout}']

    res.append('<dl class="dl-horizontal">')
    for k, v in sorted(cdict.items()):
        if k == 'cell_uuid' and cell_link:
            # Add the hyperlink
            res.append(f"<dt>{k}</dt>")
            res.append(f"<dd>[{escape_md(v)}]({cell_link})</dd>")
        elif not(k.startswith('_')):
            res.append(f"<dt>{k}</dt>")
            res.append(f"<dd>{escape_md(v)}</dd>")
    # If there is no project, we should make this explicit
    if not 'ws_project' in cdict:
        res.append("<dt>ws_project</dt>")
        res.append("<dd><span style='color: Tomato;'>None</span></dd>")
    res.append('</dl>')

    # Now add the stats table for stuff produced by fasta_stats.py
    if cdict.get('_cstats'):
        res.append('')
        res.extend(make_table(cdict['_cstats']))

    # Now add the blob and histo plots. The input data defines the plot order
    # and placement.
    for plot_section in cdict.get('_plots', []):
        for plot_group in plot_section:
            res.append(f"\n### {plot_group['title']}\n")

            # plot_group['files'] will be a list of lists, so plot
            # each list a s a row.
            for plot_row in plot_group['files']:
                res.append("<div class='flex'>")
                res.append(" ".join(
                        f"[plot](img/{p}){{.thumbnail}}"
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
                            help="Supply a list of info.yml, link.yml and .pdf files to compile into a report.")
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
