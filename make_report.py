#!/usr/bin/env python3
import os, sys, re
import logging as L
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
from datetime import datetime
from collections import OrderedDict

from smrtino import load_yaml, aggregator

""" Makes a report (in PanDoc format) for a cell. We will only report on
    processed SMRT cells where the info.yaml has been generated - so no
    reading the XML directly.
    Associated files like the CSV stats will be loaded if found (maybe I
    should link these in the YAML?)
    Run metadata can also be obtained from the pbpipeline directory.
"""

def load_input(yaml_file, links_file=None):
    """Read the provided YAML and PDF files into a dict of dicts.
       The sub-dicts are both keyed on the cell filename.
    """
    yaml_info = load_yaml(yaml_file)

    # All YAML files have a 'cell_id' which should be globally unique
    if not yaml_info.get('cell_id'):
        exit("info.yaml file must include a cell_id - eg. m54321_200211_123456")

    # Some of the items in the YAML will be references to other YAML files,
    # but we only need to look down one level.
    for k, v in yaml_info.items():
        if type(v) == str and v.startswith("@"):
            yaml_info[k] = load_yaml(v[1:], relative_to=yaml_file)
        elif type(v) == list:
            for idx in range(len(v)):
                if v[idx].startswith("@"):
                    v[idx] = load_yaml(v[idx][1:], relative_to=yaml_file)

    if links_file:
        yaml_info['_links'] = load_yaml(links_file)

    return yaml_info

def rejig_status_info(status_info, cell_data, remove=(r"Cells(Ready|Aborted|Done)", ".*Status")):
    """Re-jig the status_info into the format we want to display in the
       'About this run' section.
       This was previously done within format_report() but I broke it out.
       The result of load_input() should also be provided as cell_data
    """
    def _filter(label):
        # Returns true if the label should be filtered.
        return any( re.fullmatch(p, label) for p in [r"_.*", *remove] )

    # First eliminate anything that starts with an underscore, and 'CellsReady'
    new_info = OrderedDict([ (k, v) for k, v in status_info.items()
                              if not _filter(k) ])

    # Now add the smrtlink_qc_link at the top
    if cell_data.get('_links'):
        new_info['SMRTLink Run QC'] = ( cell_data['_links']['smrtlink_run_uuid'],
                                        cell_data['_links']['smrtlink_run_link'] )
        new_info.move_to_end('SMRTLink Run QC', last=False)

    if cell_data.get('_run'):
        # And the experiment. Also at the top
        if cell_data['_run'].get('ExperimentId'):
            new_info['Experiment'] = cell_data['_run']['ExperimentId']
            new_info.move_to_end('Experiment', last=False)

        # If the cell_data records the instrument, use this in preference
        if cell_data['_run'].get('Instrument'):
            new_info['Instrument'] = cell_data['_run']['Instrument']

    # Replace the list of cells with a count of cells, and put it to the top
    if 'Cells' in new_info:
        new_info['Cells'] = str(len(new_info['Cells'].split()))
        new_info.move_to_end('Cells', last=False)

    return new_info

def main(args):

    L.basicConfig(level=(L.DEBUG if args.debug else L.WARNING))

    yaml_data = load_input(args.yaml, args.links)

    # Glean some pipeline metadata
    pipedata = get_pipeline_metadata(args.pbpipeline)

    # And some more of that
    status_info = load_status_info(args.status)

    # Re-jig the status_info dict into the format we want to display in the
    # "About the whole run" section.
    run_status = rejig_status_info( status_info, yaml_data )

    # If there is a sample-setup.yaml file, fold in the info from that to yaml_data['reports']
    if args.sample:
        if 'reports' not in yaml_data:
            raise KeyError("Trying to add --sample data to reports, but there is no reports dict")
        add_sample_to_reports(load_yaml(args.sample), yaml_data['reports'])

    rep = format_report( yaml_data,
                         pipedata = pipedata,
                         run_status = run_status,
                         pdfreport = args.report )

    if (not args.out) or (args.out == '-'):
        print(*rep, sep="\n")
    else:
        L.info(f"Writing to {args.out}.")
        with open(args.out, "w") as ofh:
            print(*rep, sep="\n", file=ofh)

def add_sample_to_reports(sample_dict, reports_dict):
    """Adds info from sample_dict into reports_dict['Sample Loaded']
    """
    sl = reports_dict.setdefault('Sample Loaded', {})
    deets_dict = sample_dict['details']

    # FIXME - these checks are redundant as we check it in smrtlink_get_sample.py

    # Check the insert size we got from metadata.xml (in sl) versus the one we
    # see in sample-setup.yaml (sample_dict)
    if sl.get('Insert size (bp)'):
        if sl['Insert size (bp)'] != deets_dict['Insert_Size']:
            raise RuntimeError("Value mismatch in Insert Size")

    # Also check loading conc while we are at it
    if 'Loading' in reports_dict:
        if ( reports_dict['Loading']['OPLC (pM), On-Plate Loading Conc.'] !=
             deets_dict['On_Plate_Loading_Concentration'] ):
            raise RuntimeError("Value mismatch in On-Plate Loading Conc")

    # Copy the other stuff
    sl['Sample Concentration (ng/µl)'] = deets_dict['Starting_Sample_Concentration']
    sl['Sample Concentration (nM)'] = deets_dict['Sample Concentration (nM)']
    sl['Sample Volume to Use (µl)'] = deets_dict['Sample Volume to Use']
    sl['Concentration after clean-up (ng/ul)'] = None # This one is not in SMRTLink
    sl['% of recovery (anticipated)'] = deets_dict['Cleanup_Anticipated_Yield']
    sl['% of recovery (real)'] = None

    # Nothing to return - we mutated the input dict
    return

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
    # Record the current version, which should be in $SMRTINO_VERSION
    versions = set([os.environ.get('SMRTINO_VERSION','unknown')])

    if not pipe_dir:
        return dict( version = '+'.join(sorted(versions)) )

    # The start_times file reveals the previous versions applied
    try:
        with open(pipe_dir + '/start_times') as fh:
            for l in fh:
                versions.add(l.split('@')[0])
    except Exception:
        # Meh.
        pass

    # Also the name of the directory what pipe_dir is in -
    # Should be the same as the run name.
    return dict( version = '+'.join(sorted(versions)),
                 rundir = os.path.basename(os.path.realpath(pipe_dir + '/..')) )

def format_report(yaml_data, pipedata, run_status, pdfreport=None, rep_time=None):
    """ Make a full report based upon the contents of a dict of {cell_id: {infos}, ...}
        Return a list of lines to be printed as a PanDoc markdown doc.

          * yaml_data should be a dict with (opttionally) '_links' sub-dict
          * pipedata is a dict from get_pipeline_metadata()
          * run_status is a dict from rejig_status_info()
          * rep_time is a datetime but normally not needed as the current time will be used
    """
    rep = aggregator()
    time_header = (rep_time or datetime.now()).strftime("%A, %d %b %Y %H:%M")

    cell_id = yaml_data['cell_id']
    cell_links = yaml_data.get('_links', {})

    # Add title and author (ie. this pipeline) and date at the top of the report
    rep( f"% PacBio SMRT cell {escape_md(cell_id)}" )
    rep( f"% SMRTino version {pipedata.get('version')}" )
    rep( f"% {time_header}\n" )

    # Add the run_status meta-data
    run_status = run_status or {}
    rep("\n# About the whole run\n")

    rep("[⮰ Reports for all cells](./)\n")

    rep('<dl class="dl-horizontal">')

    # The dict has been pre-processed. Links will be a pair of (uuid, hyperlink)
    for k, v in run_status.items():
        rep(f"<dt>{k}</dt>")
        if type(v) is tuple:
            rep(f"<dd>[{escape_md(v[0])}]({v[1]})</dd>")
        else:
            rep(f"<dd>{escape_md(v)}</dd>")
    rep('</dl>')

    # Report all the infos and plots for this cell

    rep("", "# SMRT cell info", "")

    # See if we have a PDF and/or link to SMRTLink for this cell
    smrt_links = []
    if pdfreport:
        # \U0001F5BA is a document emoji
        smrt_links.append(f"[\U0001F5BA SMRTLink PDF report]({pdfreport}) ")
    if cell_links.get('smrtlink_cell_link'):
        smrt_links.append(f"[SMRTLink Dataset]({cell_links['smrtlink_cell_link']}) ")
    if smrt_links:
        rep("", r" \| ".join(smrt_links), "")

    # The rest of the reporting is in another function
    rep(*format_cell(yaml_data, cell_links.get('smrtlink_cell_link')))

    # Footer??
    rep("", "*~~~*")

    return rep

def blockquote(txt):
    """ Block quote some pandoc text. Returns a list of strings
    """
    return [''] + [ "> " + t for t in txt.split('\n') ] + ['']

def format_cell(cdict, cell_link=None):
    """ Format the cell infos as some sort of PanDoc output
    """
    rep = aggregator()

    # If there is no project, we should check bs_project(s). In principle
    # there could be more than one.
    projects_str = cdict.get('project')
    if not projects_str:
        projects_str = ', '.join(sorted(set([ b['bs_project']
                                              for b in cdict.get('barcodes', [])
                                              if 'bs_project' in b
                                            ])))
    if projects_str:
        projects_str = escape_md(projects_str)
    else:
        projects_str = "<span style='color: Tomato;'>None</span>"

    if 'reports' in cdict:
        # New version v2
        rep("", "## SMRTLink Sample and Reports", "")
        rep('', *make_reports_table(cdict['reports']))

    else:
        # Old version
        rep("", "## Basics", "")
        rep('<dl class="dl-horizontal">')
        for k, v in sorted(cdict.items()):
            if k == 'cell_uuid' and cell_link:
                # Add the hyperlink
                rep(f"<dt>{k}</dt>")
                rep(f"<dd>[{escape_md(v)}]({cell_link})</dd>")
            elif k == 'barcodes':
                # There will always be at least one barcode per cell, but it may
                # not have an actual 'barcode'.
                bc_str = ', '.join([b['barcode'] for b in v if 'barcode' in b])
                if bc_str:
                    rep(f"<dt>{k}</dt>")
                    rep(f"<dd>{escape_md(bc_str)}</dd>")
            elif type(v) != str:
                # Leave this for now
                pass
            elif not(k.startswith('_')):
                rep(f"<dt>{k}</dt>")
                rep(f"<dd>{escape_md(v)}</dd>")
        # If there is no project, we should check bs_project(s). In principle
        # there could be more than one.
        if not 'project' in cdict:
            # Then report projects_str which is already escaped
            rep("<dt>bs_project</dt>")
            rep(f"<dd>{projects_str}</dd>")
        rep("</dl>")

    # Now add the stats table for stuff produced by fasta_stats.py
    # This needs to be compiled for all barcodes plus unassigned
    all_cstats = [ stats_line
                   for bc in cdict.get('barcodes', [])
                   for stats_line in bc.get('_cstats', []) ]
    if cdict.get('unassigned'):
        all_cstats.extend(cdict['unassigned'].get('_cstats', []))
    if all_cstats:
        rep("", "## Read stats summary", "")
        rep('', *make_table(all_cstats))

    # Now the per-barcode formatting
    for bc in cdict.get('barcodes', []):
        if 'barcode' in bc:
            title = f"QC for barcode {bc['barcode']}"
        else:
            title = "QC for all reads"
        format_per_barcode( bc,
                            title = title,
                            aggr = rep)

    if cdict.get('unassigned'):
        format_per_barcode( cdict['unassigned'],
                            aggr = rep,
                            md_items = ["ws_name", "ws_desc", "guessed_taxon"],
                            title = "QC for unassigned reads" )

    return rep

def format_per_barcode(bc, aggr, title, md_items=None):
    """Add the plots or whatever for a single barcode to the report.

       aggr is an active aggregator object.
    """
    if md_items is None:
        # These headings make sense for most things but not unassigned
        md_items = "readset_type kinnex_type bs_project bs_name bs_desc quality_binning guessed_taxon".split()

    rep = aggr or aggregator()

    rep("", f"# {escape_md(title)}", "")

    # Info that is barcode-specific
    # TODO - maybe the list of headings should be in the YAML itself?
    rep('<dl class="dl-horizontal">')
    for k in md_items:
        if k in bc:
            rep(f"<dt>{k}</dt>")
            rep(f"<dd>{escape_md(bc.get(k,''))}</dd>")
    rep("</dl>")

    # Now add the blob and histo plots. The input data defines the plot order
    # and placement.
    for plot_section in bc.get('_plots', []):
        for plot_group in plot_section:
            rep("", f"\n### {escape_md(plot_group['title'])}\n")

            # plot_group['files'] will be a list of lists, so plot
            # each list a s a row.
            for plot_row in plot_group['files']:
                rep("<div class='flex'>")
                rep(" ".join(
                        f"[plot](img/{p}){{.thumbnail}}"
                        for p in plot_row
                    ))
                rep("</div>")

    # Return val is redundant since the lines will be added to the report.
    return rep

def make_table(rows, headings=None):
    """Yet another PanDoc table formatter oh yeah
    """
    if headings is None:
        # In this case the headings must be embedded in the first row.
        headings = rows[0]['_headings']

    def fmt(v):
        if type(v) == float:
            return "{:,.02f}".format(v)
        elif type(v) == int:
            return "{:,d}".format(v)
        else:
            return "{}".format(v)

    res = aggregator()
    res('|' + '|'.join(escape_md(h) for h in headings)  + '|')
    res('|' + '|'.join(('-' * len(escape_md(h))) for h in headings)  + '|')
    for r in rows:
        res('|' + '|'.join(escape_md(fmt(r.get(h))) for h in headings)  + '|')
    res()

    return res

def make_one_row_table(tdict):
    """Make a one-row table from a dict.
    """
    return make_table([tdict], headings=tdict.keys())

def make_reports_table(repdict):
    """Make a big melted table from the dict of dicts.
    """
    headings = ["_groupby", "Metric", "Value"]

    rows = []
    for k, v in repdict.items():
        for k2, v2 in v.items():
            rows.append( dict( _groupby = k,
                               Metric = k2,
                               Value = v2 ) )

    return make_table(rows, headings=headings)

def parse_args(*args):
    description = """Makes a report (in PanDoc format) for a run, by compiling the info from the
                     YAML files and also any extra info discovered.
                  """
    argparser = ArgumentParser( description=description,
                                formatter_class = ArgumentDefaultsHelpFormatter )
    argparser.add_argument("-y", "--yaml", required=True,
                            help="The info.yaml file to use for this report.")
    argparser.add_argument("-l", "--links",
                            help="Optional YAML links file used to make hyperlinks to SMRTLink.")
    argparser.add_argument("-r", "--report",
                            help="Optional report to link. Normally in PDF format.")
    argparser.add_argument("-p", "--pbpipeline", default="pbpipeline",
                            help="Directory to scan for pipeline meta-data.")
    argparser.add_argument("-s", "--status",
                            help="File containing status info (from pb_run_status.py) on this run.")
    argparser.add_argument("-S", "--sample",
                           help="Optional YAML sample file containing info from SMRTLink about the sample setup.")
    argparser.add_argument("-o", "--out",
                            help="Where to save the report. Defaults to stdout.")
    argparser.add_argument("-d", "--debug", action="store_true",
                            help="Print more verbose debugging messages.")

    return argparser.parse_args(*args)

if __name__ == "__main__":
    main(parse_args())
