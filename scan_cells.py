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

def my_normpath(p):
    """Call os.path.normpath but add a '/' to the name and
       convert '.' or './' to ''
    """
    if not p:
        # p can be None or ''
        return p

    p = os.path.normpath(p)

    if p == '.':
        return ''

    return p + '/'

def scan_main(args):
    """Get scanning
    """
    run_name = os.path.basename(os.path.realpath(args.rundir))
    parsed_run_name = parse_run_name(run_name)

    res = dict( run = parsed_run_name,
                cells = {} )

    # How to decide if the cell is ready?
    # We can't scan for metadata as there are multiple of those files
    extn_to_scan = ".sts.xml" if args.xmltrigger else ".transferdone"

    assert parsed_run_name['run_or_cell'] == 'run'
    if parsed_run_name['platform'].startswith("Sequel"):
        sc = scan_cells_sequel( my_normpath(args.rundir),
                                args.cells,
                                extn_to_scan )
    else:
        sc = scan_cells_revio( my_normpath(args.rundir),
                               args.cells,
                               extn_to_scan,
                               args.redemux and my_normpath(args.redemux) )

    res['cells'].update(sc)

    return res


def scan_cells_revio(rundir, cell_list, extn_to_scan=".transferdone", redemux=None):
    """ Here's what we want to find, per cell.
        .transferdone - is under metadata
        {cell}.reads.bam - under hifi_reads and fail_reads
        {cell}.reads.bam.pbi - ditto
        {cell}.consensusreadset.xml - under pb_formats
        {cell}.metadata.xml - under metadata
        {cell}.reports.zip - ditto
        {cell}.lima_counts.txt - ditto, but optional

        If redemux_dir is set and exists this overrides:
            {cell}.reads.bam[.pbi]
            {cell}.consensusreadset.xml
            {cell}.lima_counts.txt (if it exists, and note the rename)

    """
    # Get a dict of slot: cell for all cells
    all_cells = { b.split('/')[-3]: b.split('/')[-1][:-len(extn_to_scan)]
                  for b in glob(f"{rundir}*/metadata/*{extn_to_scan}") }

    if cell_list:
        all_cells = { k:all_cells[k] for k in cell_list }

    # Now we can make a result, keyed off cell ID (not the slot)
    res = dict()
    for slot, cellid in all_cells.items():
        res[cellid] = { 'slot': slot,
                        'parts': ['hifi_reads', 'fail_reads'] }
        if redemux is None:
            redemux_dir = None
            res[cellid]['re-demultiplex'] = False
        else:
            redemux_dir = redemux.format(slot=slot, cell=cellid, cellid=cellid)
            # This is needed as os.path.isdir('') always returns False
            res[cellid]['re-demultiplex'] = os.path.isdir(redemux_dir or '.')
        if res[cellid]['re-demultiplex']:
            res[cellid].update({
                    'barcodes': find_barcodes_redemux(redemux_dir, cellid),
                    'meta': find_meta(rundir, slot, cellid),
                    'reports_zip': find_reports_zip(rundir, slot, cellid),
                    'lima_counts': find_lima_counts_redemux(redemux_dir, cellid) })
        else:
            res[cellid].update({
                    'barcodes': find_barcodes(rundir, slot, cellid),
                    'meta': find_meta(rundir, slot, cellid),
                    'reports_zip': find_reports_zip(rundir, slot, cellid),
                    'lima_counts': find_lima_counts(rundir, slot, cellid) })

    # Add unassigned, and unbarcoded ('all'), possibly
    for cellid, v in res.items():
        if 'unassigned' in v['barcodes']:
            # Move it out
            v['unassigned'] = v['barcodes']['unassigned']
            del v['barcodes']['unassigned']

        if not res[cellid]['re-demultiplex']:
            v['barcodes'].update(find_unbarcoded(rundir, v['slot'], cellid))

    # Sanity check on lima_counts
    for cellid, v in res.items():
        if v.get('lima_counts') and not v.get('unassigned'):
            L.warning("We have lima_counts but no unassigned")
        if v.get('unassigned') and not v.get('lima_counts'):
            # This is worse
            raise RuntimeError("We have unassigned but no lima_counts")

    return res

def find_barcodes_redemux(redemux_dir, cellid, check_exist=True):
    """Finds the data files and .consensusreadset.xml files for re-demultiplexing jobs
       in SMRTLink.

       For some reason the "unassigned" barcodes get called "unbarcoded" and also live
       in the top level directory so I have to account for that naming.
    """
    # At this point I'm not checking that the directory name matches the file name,
    # but files_per_barcode_redemux() will spot any anomalies.
    xmlfiles = glob(f"{redemux_dir}*/{cellid}.hifi_reads.*.consensusreadset.xml")
    barcodes = [ os.path.basename(f)[len(f"{cellid}.hifi_reads."):-len(".consensusreadset.xml")]
                 for f in xmlfiles ]

    res = { bc: files_per_barcode_redemux(redemux_dir, cellid, bc, check_exist)
            for bc in barcodes }

    if ('unassigned' in res) or ('unbarcoded' in res):
        raise RuntimeError("Did not expect to find 'unassigned' barcodes in subdirectories"
                           "of re-demultiplex dir")

    # But we do expect to find 'unbarcoded' reads
    res['unassigned'] = unassigned_for_redemux(redemux_dir, cellid, check_exist)

    return res

def find_barcodes(rundir, slot, cellid, check_exist=True):
    """Find the data files by barcode by globbing the files. Could also check the XML
       to get this, but that doesn't work for re-demultiplexing.

       In Revio, "default" is regarded as a barcode but "unassigned" is
       special. We feel this may change in later releases.
    """

    # Previously I was globbing the BAM files, but I think I'll glob the metadata files
    # instead. Probably makes no difference.
    # eg: 1_C01/pb_formats/m84140_231018_155043_s3.hifi_reads.bc1002.consensusreadset.xml

    xmlfiles = glob(f"{rundir}{slot}/pb_formats/{cellid}.hifi_reads.*.consensusreadset.xml")
    barcodes = [ os.path.basename(f)[len(f"{cellid}.hifi_reads."):-len(".consensusreadset.xml")]
                 for f in xmlfiles ]

    res = { bc: files_per_barcode(rundir, slot, cellid, bc, check_exist)
            for bc in barcodes }

    return res

def find_unbarcoded(rundir, slot, cellid, check_exist=True):
    """With SMRTLink 13 we're back to having unbarcoded files. But to avoid a load of
       if/else logic I'm going to assign these to a barcode named "all".

       Not to be confused with 'unbarcoded' reads in SMRTLink which are really 'unassigned'.
    """
    # I guess I could stick with the logic of Hesiod and make a bracode named "." but
    # I think this ended up being a bit confusing.
    # We have to look for the BAM file directly because even barcoded runs have a
    # combined hifi_reads.consensusreadset.xml file.

    hifipath = f"{rundir}{slot}/hifi_reads"
    bamfiles = glob(f"{hifipath}/{cellid}.hifi_reads.bam")

    res = {}
    if bamfiles:
        res['all'] = files_per_barcode(rundir, slot, cellid, None, check_exist)

    return res

def unassigned_for_redemux(redemux_dir, cellid, check_exist=True):
    """Gets the unassigned (aka. unbarcoded) reads from redemux_dir

       TODO - maybe I could also look for 'unassigned'. But I really don't expect to
       find those.
    """
    hifi = dict( bam = f"{redemux_dir}{cellid}.hifi_reads.unbarcoded.bam",
                 pbi = f"{redemux_dir}{cellid}.hifi_reads.unbarcoded.bam.pbi",
                 xml = f"{redemux_dir}{cellid}.hifi_reads.unbarcoded.consensusreadset.xml" )
    fail = dict( bam = f"{redemux_dir}{cellid}.fail_reads.unbarcoded.bam",
                 pbi = f"{redemux_dir}{cellid}.fail_reads.unbarcoded.bam.pbi" )

    if check_exist:
        for f in chain(hifi.values(), fail.values()):
            if not os.path.exists(f):
                raise FileNotFoundError(f"missing {f}")

    return dict( hifi_reads = hifi,
                 fail_reads = fail )


def files_per_barcode_redemux(redemux_dir, cellid, barcode, check_exist=True):
    """Returns the location of the reads files for a given barcode,
       and checks they exist (redemux mode).
    """
    hifi = dict( bam = f"{redemux_dir}{barcode}/{cellid}.hifi_reads.{barcode}.bam",
                 pbi = f"{redemux_dir}{barcode}/{cellid}.hifi_reads.{barcode}.bam.pbi",
                 xml = f"{redemux_dir}{barcode}/{cellid}.hifi_reads.{barcode}.consensusreadset.xml" )
    fail = dict( bam = f"{redemux_dir}{barcode}/{cellid}.fail_reads.{barcode}.bam",
                 pbi = f"{redemux_dir}{barcode}/{cellid}.fail_reads.{barcode}.bam.pbi" )

    if check_exist:
        for f in chain(hifi.values(), fail.values()):
            if not os.path.exists(f):
                raise FileNotFoundError(f"missing {f}")

    return dict( hifi_reads = hifi,
                 fail_reads = fail )

def files_per_barcode(rundir, slot, cellid, barcode, check_exist=True):
    """Returns the location of the reads files for a given barcode,
       and checks they exist.
    """
    barcode = f".{barcode}" if barcode else ""

    hifi = dict( bam = f"{rundir}{slot}/hifi_reads/{cellid}.hifi_reads{barcode}.bam",
                 pbi = f"{rundir}{slot}/hifi_reads/{cellid}.hifi_reads{barcode}.bam.pbi",
                 xml = f"{rundir}{slot}/pb_formats/{cellid}.hifi_reads{barcode}.consensusreadset.xml" )
    fail = dict( bam = f"{rundir}{slot}/fail_reads/{cellid}.fail_reads{barcode}.bam",
                 pbi = f"{rundir}{slot}/fail_reads/{cellid}.fail_reads{barcode}.bam.pbi" )

    if check_exist:
        for f in chain(hifi.values(), fail.values()):
            if not os.path.exists(f):
                raise FileNotFoundError(f"missing {f}")

    return dict( hifi_reads = hifi,
                 fail_reads = fail )

def find_meta(rundir, slot, cellid):
    """Returns the location of the .metadata.xml, and checks it exists.
    """
    res = f"{rundir}{slot}/metadata/{cellid}.metadata.xml"

    if not os.path.exists(res):
        raise FileNotFoundError(f"missing {res}")

    return res

def find_reports_zip(rundir, slot, cellid, check_exist=True):
    """Returns the location of the .metadata.xml, and checks it exists.
    """
    res = f"{rundir}{slot}/statistics/{cellid}.reports.zip"

    if check_exist:
        if not os.path.exists(res):
            raise FileNotFoundError(f"missing {res}")

    return res

def find_lima_counts_redemux(redemux_dir, cellid, check_exist=True):
    """Returns the location of the lima_counts.txt file which in this case
       is missing the .txt extension. And it's an error if it does not exist.
    """
    res = f"{redemux_dir}{cellid}.hifi_reads.lima.counts" # ignoring the fail_reads counts here

    if check_exist:
        if not os.path.exists(res):
            raise FileNotFoundError(f"missing {res}")

    return res

def find_lima_counts(rundir, slot, cellid):
    """Returns the location of the lima_counts.txt file found under
       statistics. If there is no such file, returns None.
    """
    res = f"{rundir}{slot}/statistics/{cellid}.hifi_reads.lima_counts.txt"

    if not os.path.exists(res):
        return None

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
                  for b in glob(f"{rundir}*/*{extn_to_scan}") }

    # Now see if I need to filter by cell_list.
    if cell_list:
        all_cells = [ c for c in all_cells if c[0] in cell_list ]

    # Note that the list of cells could well be empty.
    res = { cellid: { 'slot':  slot,
                      'parts': None,
                      'meta':  f"{rundir}{slot}/.{cellid}.metadata.xml"
                    } for slot, cellid in all_cells.items() }

    # Assume no barcodes, and all reads are "default".
    # We don't really need this to work anyways - it's just for comparison.
    for cellid, cellinfo in res.items():
        if not os.path.exists(cellinfo['meta']):
            raise FileNotFoundError(f"missing {cellinfo['meta']}")

        parts = determine_parts_sequel(rundir, cellinfo['slot'], cellid)
        cellinfo['parts'] = sorted(parts, reverse=True)
        cellinfo['barcodes'] = dict(default=parts)

    return res

def determine_parts_sequel(rundir, slot, cellid):
    """Work out if this is a ['subreads', 'scraps'] cell or a ['reads'] cell.
    """
    cellpath = f"{rundir}{slot}/{cellid}"
    bamfiles = glob(f"{cellpath}.*.bam")

    def get_xml(slot, cellid, part):
        if part == "subreads":
            return dict(xml = f"{slot}/{cellid}.subreadset.xml")
        elif part == "reads":
            return dict(xml = f"{slot}/{cellid}.consensusreadset.xml")
        else: # part == "scraps":
            return dict()

    parts = { part:
              dict( bam = f"{rundir}{slot}/{cellid}.{part}.bam",
                    pbi = f"{rundir}{slot}/{cellid}.{part}.bam.pbi",
                    **get_xml(slot, cellid, part) )
              for b in bamfiles
              for part in [b[len(f"{cellpath}."):-len(".bam")]] }

    assert parts, f"No .bam files found matching {cellpath}.*.bam"
    for p in parts:
        for d in parts.values():
            for f in d.values():
                # Ensure file exists
                os.stat(f)

    return parts

def parse_args(*args):
    description = """Scan the input files for all SMRT cells, to provide a work plan for Snakemake
                  """

    parser = ArgumentParser( description = description,
                             formatter_class = ArgumentDefaultsHelpFormatter)

    parser.add_argument("rundir", default='./pbpipeline/from', nargs='?',
                        help="Directory to scan for cells and their data files")

    parser.add_argument("--redemux", default='./pbpipeline/re-demultiplex-{cell}',
                        help="Directory to scan for SMRTLink re-demultiplex of the run, which should be the"
                             " jobs_root/xxxx/outputs/demultiplexing_files directory in SMRTLink.")

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

