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

    assert parsed_run_name['run_or_cell'] == 'run'
    if parsed_run_name['platform'].startswith("Sequel"):
        sc = scan_cells_sequel(args.rundir, args.cells)
    else:
        sc = scan_cells_revio(args.rundir, args.cells)

    res['cells'].update(sc)

    return res


def scan_cells_revio(rundir, cell_list):
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
    all_cells = { b.split('/')[-3]: b.split('/')[-1][:-len('.transferdone')]
                  for b in glob(f"{rundir}/*/metadata/*.transferdone") }

    if cell_list:
        all_cells = { k:all_cells[k] for k in cell_list }

    # Now we can make a result, keyed off cell ID (not slot)
    res = { cellid: { 'slot': slot,
                      'parts': ['reads_hifi', 'reads_fail'],
                      'barcodes': find_barcodes(rundir, slot, cellid),
                      'unassigned': files_per_barcode(rundir, slot, cellid, "unassigned"),
                      'meta': find_meta(rundir, slot, cellid)
                    } for slot, cellid in all_cells.items() }

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
            for bc in barcodes
            if bc != "unassigned" }

    return res

def files_per_barcode(rundir, slot, cellid, barcode):
    """Returns the location of the reads files for a given barcode, including "unassigned",
       and checks they exits.
    """
    hifi = dict( bam = f"{slot}/hifi_reads/{cellid}.hifi_reads.{barcode}.bam",
                 pbi = f"{slot}/hifi_reads/{cellid}.hifi_reads.{barcode}.bam.pbi",
                 xml = f"{slot}/pb_formats/{cellid}.hifi_reads.{barcode}.consensusreadset.xml" )
    fail = dict( bam = f"{slot}/fail_reads/{cellid}.fail_reads.{barcode}.bam",
                 pbi = f"{slot}/fail_reads/{cellid}.fail_reads.{barcode}.bam.pbi",
                 xml = f"{slot}/pb_formats/{cellid}.fail_reads.{barcode}.consensusreadset.xml" )

    assert all( os.path.exists(f"{rundir}/{f}")
                for f in chain(hifi.values(), fail.values()) )

    return dict( reads_hifi = hifi,
                 reads_fail = fail )

def find_meta(rundir, slot, cellid):
    """Returns the location of the .metadata.xml, and checks it exists.
    """
    res = f"{slot}/metadata/{cellid}.metadata.xml"

    assert os.path.exists(f"{rundir}/{res}")

    return res

def scan_cells_sequel(rundir, cell_list):
    """ Work out all the cells to process based on config['cells'] and config['rundir']
        and thus infer the base names  of the info.yml files that need to be made.
        Return a dict of:
            cell_id->{'slot': slot_id, 'filter': '', 'parts': [...]}.
        This in turn allows me to work out everything else by pattern matching. Note that
        no filter is currently supported but I left this feature in just in case.
        When run on a GSEG worker node this list will come out empty, but that's
        OK.
    """
    all_cells = { b.split('/')[-2]: b.split('/')[-1][:-len('.transferdone')]
                  for b in glob(f"{rundir}/*/*.transferdone") }

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

    # TODO. Delete this, I think. Maybe? None-ready cells are just invisible,
    #parser.add_argument("-r", "--cellsready", nargs='+',
    #                    help="Cells to process now. If not specified, the script will check.")

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
