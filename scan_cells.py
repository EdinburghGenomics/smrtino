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

    # TODO
    return {}

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
    all_done = [ b[:-len('.transferdone')] for b in glob(f"{rundir}/*/*.transferdone") ]

    # Now see if I need to filter by cell_list.
    if cell_list:
        all_done = [ s for s in all_done if s.split('/')[-2] in cell_list ]

    # Note that the list of cells could well be empty.
    res = { r.split('/')[-1]: { 'slot':   r.split('/')[-2],
                                'parts':  determine_parts(r)
                              } for r in all_done }

    return res

def determine_parts(cellpath):
    """Work out if this is a ['subreads', 'scraps'] cell or a ['reads'] cell.
    """
    bamfiles = glob(cellpath + '.*.bam')
    parts = [ b[len(cellpath + '.'):-len('.bam')] for b in bamfiles ]

    assert parts, f"No .bam files found matching {cellpath}.*.bam"
    # Fix the order. This works.
    return sorted(parts, reverse=True)

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

