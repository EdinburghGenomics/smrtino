#!/usr/bin/env python3

"""This script generates sc_data.yaml on STDOUT.

   It does not modify anything - you can run it in any Revio (or Sequel2)
   run directory like:

   $ scan_cells.py /path/to/examine

   Even though the pipeline as a whole will not support Sequel runs,
   I want to support them here so I can compare the old and new directory
   formats.
"""
import os, sys, re
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
import logging as L
from functools import partial
from itertools import chain
from pprint import pprint, pformat

from smrtino import ( glob, parse_run_name, dump_yaml )

def main(args):

    L.basicConfig( level = L.DEBUG if args.verbose else L.INFO,
                         format = "{levelname}:{message}",
                         style = '{' )

    if not args.missing_ok and not glob(f"{args.rundir}/."):
        exit(f"No such directory {args.rundir}. Use -m to look for output files in CWD.")

    # Call scan_main, which is amenable to testing
    res = scan_main(args)

    print( dump_yaml(res), end='' )

def scan_main(args):
    """Get scanning
    """
    run_name = os.path.basename(os.path.realpath(args.rundir))
    parsed_run_name = parse_run_name(run_name)

    res = dict( run = parsed_run_name,
                cells = {} )

    # We can't scan for metadata as there are multiple of those files
    extn_to_scan = ".sts.xml" if args.xmltrigger else ".transferdone"

    assert parsed_run_name['run_or_cell'] == 'run'
    if parsed_run_name['platform'].startswith("Sequel"):
        sc = scan_cells_sequel(args.rundir, args.cells, extn_to_scan)
    else:
        sc = scan_cells_revio(args.rundir, args.cells, extn_to_scan)

    res['cells'].update(sc)

    return res


def scan_cells_revio(rundir, cell_list, extn_to_scan=".transferdone"):
    """ Here's what we want to find, per cell.
        .transferdone - is under metadata
        {cell}.reads.bam - under hifi_reads. I guess the fail reads are the <Q20 reads
                           Do we still have the option to include kinetics??
                           Well apparently they are included already (says Heleen)
        {cell}.reads.bam.pbi - yep we get PBI files
        {cell}.consensusreadset.xml - under pb_formats
        .{cell}.run.metadata.xml - Seems to be gone? Or is it m84140_230823_180019_s1.metadata.xml?
    """
    # Get a dict of slot: cell for all cells
    all_cells = { b.split('/')[-3]: b.split('/')[-1][:-len(extn_to_scan)]
                  for b in glob(f"{rundir}/*/metadata/*{extn_to_scan}") }

    if cell_list:
        all_cells = { k:all_cells[k] for k in cell_list }

    # Now we can make a result, keyed off cell ID (not slot)
    res = { cellid: { 'slot': slot,
                      'parts': ['hifi_reads', 'fail_reads'],
                      'barcodes': find_barcodes(rundir, slot, cellid),
                      'meta': find_meta(rundir, slot, cellid),
                      'reports_zip': find_reports_zip(rundir, slot, cellid),
                    } for slot, cellid in all_cells.items() }
    # Add unassigned, and unbarcoded ('all'), possibly
    for cellid, v in res.items():
        if 'unassigned' in v['barcodes']:
            # Move it out
            v['unassigned'] = v['barcodes']['unassigned']
            del v['barcodes']['unassigned']

        v['barcodes'].update(find_unbarcoded(rundir, v['slot'], cellid))

    return res

def find_barcodes(rundir, slot, cellid):
    """Find the barcodes used by globbing the files. Could also check the XML.

       In Revio, "default" is regarded as a barcode but "unassigned" is
       special. We feel this may change in later releases.
    """

    # Previously I was globbing the BAM files, but I think I'll glob the matadata files
    # instead. Probably makes no difference.
    # eg: 1_C01/pb_formats/m84140_231018_155043_s3.hifi_reads.bc1002.consensusreadset.xml

    xmlpath = f"{rundir}/{slot}/pb_formats"
    xmlfiles = glob(f"{xmlpath}/{cellid}.hifi_reads.*.consensusreadset.xml")
    barcodes = [ f[len(f"{xmlpath}/{cellid}.hifi_reads."):-len(".consensusreadset.xml")]
                 for f in xmlfiles ]

    res = { bc: files_per_barcode(rundir, slot, cellid, bc)
            for bc in barcodes }

    return res

def find_unbarcoded(rundir, slot, cellid):
    """With SMRTLink 13 we're back to having unbarcoded files. But to avoid a load of
       if/else logic I'm going to assign these to a barcode named "all".
    """
    # I guess I could stick with the logic of Hesiod and make a bracode named "." but
    # I think this ended up being a bit confusing.
    # We have to look for the BAM file directly because even barcoded runs have a
    # combined hifi_reads.consensusreadset.xml file.

    hifipath = f"{rundir}/{slot}/hifi_reads"
    bamfiles = glob(f"{hifipath}/{cellid}.hifi_reads.bam")

    res = {}
    if bamfiles:
        res['all'] = files_per_barcode(rundir, slot, cellid, None)

    return res

def files_per_barcode(rundir, slot, cellid, barcode, check_exist=True):
    """Returns the location of the reads files for a given barcode,
       and checks they exist.
    """
    barcode = f".{barcode}" if barcode else ""

    hifi = dict( bam = f"{slot}/hifi_reads/{cellid}.hifi_reads{barcode}.bam",
                 pbi = f"{slot}/hifi_reads/{cellid}.hifi_reads{barcode}.bam.pbi",
                 xml = f"{slot}/pb_formats/{cellid}.hifi_reads{barcode}.consensusreadset.xml" )
    fail = dict( bam = f"{slot}/fail_reads/{cellid}.fail_reads{barcode}.bam",
                 pbi = f"{slot}/fail_reads/{cellid}.fail_reads{barcode}.bam.pbi" )

    if check_exist:
        for f in chain(hifi.values(), fail.values()):
            assert os.path.exists(f"{rundir}/{f}"), f"missing {rundir}/{f}"

    return dict( hifi_reads = hifi,
                 fail_reads = fail )

def find_meta(rundir, slot, cellid):
    """Returns the location of the .metadata.xml, and checks it exists.
    """
    res = f"{slot}/metadata/{cellid}.metadata.xml"

    assert os.path.exists(f"{rundir}/{res}"), f"missing {rundir}/{res}"

    return res

def find_reports_zip(rundir, slot, cellid):
    """Returns the location of the .metadata.xml, and checks it exists.
    """
    res = f"{slot}/statistics/{cellid}.reports.zip"

    assert os.path.exists(f"{rundir}/{res}"), f"missing {rundir}/{res}"

    return res

def scan_cells_sequel(rundir, cell_list, extn_to_scan=".transferdone"):
    """ Work out all the cells to process based on config['cells'] and config['rundir']
        and thus infer the base names of the info.yaml files that need to be made.
        Return a dict of:
            cell_id->{'slot': slot_id, 'filter': '', 'parts': [...]}.
        This in turn allows me to work out everything else by pattern matching. Note that
        no filter is currently supported but I left this feature in just in case.
    """
    all_cells = { b.split('/')[-2]: b.split('/')[-1][:-len(extn_to_scan)]
                  for b in glob(f"{rundir}/*/*{extn_to_scan}") }

    # Now see if I need to filter by cell_list.
    if cell_list:
        all_cells = [ c for c in all_cells if c[0] in cell_list ]

    # Note that the list of cells could well be empty.
    res = { cellid: { 'slot':  slot,
                      'parts': None,
                      'meta':  f"{slot}/.{cellid}.metadata.xml"
                    } for slot, cellid in all_cells.items() }

    # Assume no barcodes, and all reads are "default".
    # We don't really need this to work anyways - it's just for comparison.
    for cellid, cellinfo in res.items():
        assert os.path.exists(f"{rundir}/{cellinfo['meta']}")

        parts = determine_parts_sequel(rundir, cellinfo['slot'], cellid)
        cellinfo['parts'] = sorted(parts, reverse=True)
        cellinfo['barcodes'] = dict(default=parts)

    return res

def determine_parts_sequel(rundir, slot, cellid):
    """Work out if this is a ['subreads', 'scraps'] cell or a ['reads'] cell.
    """
    cellpath = f"{rundir}/{slot}/{cellid}"
    bamfiles = glob(f"{cellpath}.*.bam")

    def get_xml(slot, cellid, part):
        if part == "subreads":
            return dict(xml = f"{slot}/{cellid}.subreadset.xml")
        elif part == "reads":
            return dict(xml = f"{slot}/{cellid}.consensusreadset.xml")
        else: # part == "scraps":
            return dict()

    parts = { part:
              dict( bam = f"{slot}/{cellid}.{part}.bam",
                    pbi = f"{slot}/{cellid}.{part}.bam.pbi",
                    **get_xml(slot, cellid, part) )
              for b in bamfiles
              for part in [b[len(f"{cellpath}."):-len(".bam")]] }

    assert parts, f"No .bam files found matching {cellpath}.*.bam"
    for p in parts:
        for d in parts.values():
            for f in d.values():
                # Ensure file exists
                os.stat(f"{rundir}/{f}")

    return parts

def parse_args(*args):
    description = """Scan the input files for all SMRT cells, to provide a work plan for Snakemake
                  """

    parser = ArgumentParser( description = description,
                             formatter_class = ArgumentDefaultsHelpFormatter)

    parser.add_argument("rundir", default='./pbpipeline/from', nargs='?',
                        help="Directory to scan for cells and their data files")

    parser.add_argument("-c", "--cells", nargs='+',
                        help = "Cells to look at. If not specified, all will be scanned."
                               " Give the slot not the cell ID - eg. 1_A01" )

    parser.add_argument("-x", "--xmltrigger", action="store_true",
                        help="Identify ready cells by .sts.xml presence, not .transferdone.")

    # The point of this is that if the pipeline is being re-run, ./pbpipeline/from may have been
    # deleted but we can still look at the outut files to reconstruct the info. But unless the
    # pipeline has previously run and copied all the data then trying to look in the current dir
    # will see nothing, or incomplete data.
    parser.add_argument("-m", "--missing_ok", action="store_true",
                        help="If rundir is missing or incomplete, scan files in current dir.")

    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Print more logging to stderr")

    return parser.parse_args(*args)

if __name__=="__main__":
    main(parse_args())

