#!/usr/bin/env python3
import os, sys, re
import logging as L
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter

from smrtino import glob, aggregator
from smrtino.ParseXML import get_readset_info

""" Makes a summary (in text format) for a run.
    This is somewhat similar to make_report.py, but it runs on the original directory
    and does not depend on any pipeline output. It reads the XML files directly, using
    the same library as compile_cell_info.py.

    Unlike make_report, this does not want to be supplied with a list of .yml files,
    but rather it will scan for available data.
"""

def main(args):

    L.basicConfig(level=(L.DEBUG if args.debug else L.WARNING))

    # This will be by slot, not by cell ID, as we're not sure we even know the cell IDs.
    all_info = dict()

    scanpattern = f"{args.dir}/*/"

    replinks = load_replinks(args.replinks)

    # Look for a subdirs that look like slot names (eg. 1_A01)
    for slot_dir in glob(scanpattern):
        mo = re.search(r'/(\d_[A-Z]\d\d)$', slot_dir)
        if mo:
            slot = mo.group(1)
        else:
            continue
        all_info[slot] = dict()

        # Load the XML, if found
        srs_xml = glob(f"{slot_dir}/*.*readset.xml")
        if len(srs_xml) > 1:
            L.error(f"Multiple .*readset.xml found for slot {slot}")
        elif srs_xml:
            srs_xml, = srs_xml

            xml_info = get_readset_info(srs_xml)

            all_info[slot].update(xml_info)

        # Link to the report, if found
        all_info[slot]['report'] = replinks.get(slot)

    rep = format_summary(all_info, run_id=args.runid, run_dir=os.path.realpath(args.dir))

    if (not args.txt) or (args.txt == '-'):
        print(*rep, sep="\n")
    else:
        L.info(f"Writing to {args.out}.")
        with open(args.txt, "w") as ofh:
            print(*rep, sep="\n", file=ofh)

def load_replinks(replinks_file):
    """Load the links from the report_upload_url.txt file, if supplied.
       Ideally this would be a YAML already but the upload_report.sh is not clever
       enough to make one, so reconstruct a dict based on the filenames, which must
       start with the slot names.
    """
    res = dict()

    if not replinks_file:
        return res

    try:
        with open(replinks_file) as fh:
            for aline in fh:
                aline = aline.strip()
                mo = re.search(r'/([^-/]+)-[^/]+$', aline)
                if mo:
                    res[mo.group(1)] = aline
    except FileNotFoundError as e:
        # I'm not sure if this should be a fatal error. Probably not.
        L.exception(e)
        pass

    return res

def format_summary(all_info, run_id=None, run_dir='.'):
    """ Make a summary report based upon the contents of a dict of {slot_id: {infos}, ...}
        Return a list of lines to be included in a summary sent to RT
    """
    # Sanity check all_info has some info
    if not all_info:
        return [f"No SMRT Cells found in {os.getcwd()}"]

    # Sanity-check the run_id is consistently reported.
    run_id_set = set(i['run_id'] for i in all_info.values() if i.get('run_id'))
    if run_id:
        run_id_set.add(run_id)
    try:
        run_id, = run_id_set
    except ValueError:
        exit(f"Cannot determine Run ID. Please supply a --runid consistent with {run_id_set}.")

    replines = aggregator( run_dir,
                           f"holds run {run_id} with {len(all_info)} SMRT cells" )

    for k, v in sorted(all_info.items()):

        replines()
        replines(f"Slot *{k}*:")
        replines(f"  Cell ID: {v.get('cell_id', 'unknown')}")
        replines(f"  Sample : {v.get('ws_name', 'unknown')}")
        replines(f"  Report : {v.get('report') or 'none yet'}")

    return replines

def parse_args(*args):
    description = """ Makes a summary (in text format) for a run, by scanning the directory.
                      Unlike make_report.py, this one always runs on the original source dir,
                      not the output directory, and does not save/use any intermediate YAML
                      files, though it does try to read the XML.
                  """
    argparser = ArgumentParser( description=description,
                                formatter_class = ArgumentDefaultsHelpFormatter )
    argparser.add_argument("--txt",
                            help="Where to save the textual report. Defaults to stdout.")
    argparser.add_argument("--dir", default=".",
                            help="Where to scan, if not the current dir.")
    argparser.add_argument("--runid",
                            help="Hint what we expect the run ID to be.")
    argparser.add_argument("--replinks",
                            help="File with HTML links to reports, one per line.")
    argparser.add_argument("-d", "--debug", action="store_true",
                            help="Print more verbose debugging messages.")

    return argparser.parse_args(*args)

if __name__ == "__main__":
    main(parse_args())
