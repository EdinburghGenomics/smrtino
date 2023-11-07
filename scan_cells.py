#!/usr/bin/env python3

"""This script generates sc_data.yaml on STDOUT.

   It does not modify anything - you can run it in any Revio (or Sequel2)
   run directory like:

   $ scan_cells.py /path/to/examine
"""

from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
import logging as L
from functools import partial
from pprint import pprint, pformat

from smrtino import ( glob, groupby, parse_cell_name, dump_yaml )

def main(args):

    L.basicConfig( level = L.DEBUG if args.verbose else L.INFO,
                         format = "{levelname}:{message}",
                         style = '{' )

    if not args.missing_ok and not glob(f"{args.expdir}/."):
        exit(f"No such directory {args.expdir}. Use -m to look for output files in CWD.")

    # Call scan_main, which is amenable to testing
    res = scan_main(args)

    print( dump_yaml(res), end='' )

def is_sequel_run(parsed_run_name):
    """Decide if we think this is a sequel run.
    """
    # I could do this by examining the files, but I think I'll do it by looking at the
    # run name.




def scan_cells_revio(expdir):

def scan_cells_sequel(expdir):
    """ Work out all the cells to process based on config['cells'] and config['rundir']
        and thus infer the base names  of the info.yml files that need to be made.
        Return a dict of:
            cell_id->{'slot': slot_id, 'filter': '', 'parts': [...]}.
        This in turn allows me to work out everything else by pattern matching. Note that
        no filter is currently supported but I left this feature in just in case.
        When run on a GSEG worker node this list will come out empty, but that's
        OK.
    """
    all_done = [ b[:-len('.transferdone')] for b in glob('{}/*/*.transferdone'.format(RUNDIR) ) ]

    # Now see if I need to filter by config['cells']
    if 'cells' in config:
        res = [ s for s in all_done if s.split('/')[-2] in config['cells'].split() ]
    else:
        res = all_done

    if not ('--no-hooks' in sys.argv or config.get('ignore_missing')):
        # A hacky way of having an assertion only on the master process.
        assert res, "No subreads found in {} matching cell [{}].".format(RUNDIR, config.get('cells', '*'))

    return { r.split('/')[-1]: { 'slot':   r.split('/')[-2],
                                 'filter': determine_filter(r),
                                 'parts':  determine_parts(r) } for r in res }

def parse_args(*args):
    description = """Scan the input files for all cells, to provide a work plan for Snakemake"""

    parser = ArgumentParser( description = description,
                             formatter_class = ArgumentDefaultsHelpFormatter)

    parser.add_argument("expdir", default='./pbpipeline/from', nargs='?',
                        help="Directory to scan for cells and their data files")

    parser.add_argument("-c", "--cells", nargs='+',
                        help="Cells in this run. If not specified, all will be scanned.")
    parser.add_argument("-r", "--cellsready", nargs='+',
                        help="Cells to process now. If not specified, the script will check.")

    # The point of this is that if the pipeline is being re-run, ./pbpipeline/from may have been
    # deleted but we can still look at the outut files to reconstruct the info. But unless the
    # pipeline has previously run and copied all the data then trying to look in the current dir
    # will see nothing, or incomplete data.
    parser.add_argument("-m", "--missing_ok", action="store_true",
                        help="If expdir is missing or incomplete, scan files in current dir.")

    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Print more logging to stderr")

    return parser.parse_args(*args)

