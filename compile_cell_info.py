#!/usr/bin/env python3
import os, sys
import logging as L
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter

from smrtino import load_yaml, dump_yaml

""" The info needed to report on a SMRT cell consists of several YAML files:
        sc_data.yaml about the files in the upstream
        unassigned.yaml about the unassigned reads (if applicable)
        bc1.yaml bc2.yaml about the barcodes.

    This super-simple script just outputs a file linking to these other files.
"""

def main(args):

    L.basicConfig(level=(L.DEBUG if args.debug else L.WARNING), stream=sys.stderr)

    # Build the links to the files.
    info = gen_info(args)

    if args.extract_ids:
        info.update(extract_ids_multi(args.bcfiles))

    dump_yaml(info, fh=sys.stdout)

def extract_ids_multi(yaml_files):
    """Run extract_ids() on each of the YAML files and verify that
       the result is the same in all cases, and return the resulting dict.
    """
    extracted_ids = extract_ids(yaml_files[0])

    for yf in yaml_files[1:]:
        alt_ids = extract_ids(yf)

        if alt_ids != extracted_ids:
            raise RuntimeError(f"extract_ids({yaml_files[0]}) mismatch with extract_ids({yf}):\n"
                               f"{extracted_ids}\nvs\n{alt_ids}")

    return extracted_ids


def extract_ids(yaml_file):
    """Pull some bits needed for link_to_smrtlink.py
    """
    ydata = load_yaml(yaml_file)

    return { k: ydata[k]
             for k in '''run_id run_slot cell_id cell_uuid
                         ws_name ws_desc'''.split() }

def gen_info(args):

    res = dict()
    for k in ['sc_data', 'unassigned']:
        v = getattr(args, k)
        if v and v != "-":
            res[k] = check_exists(v, args.check_yaml)

    # If args.extract_ids is set then there's no point in loading the YAML twice.
    check_bcfile_yaml = args.check_yaml and (not args.extract_ids)
    res['barcodes'] = [ check_exists(f, check_bcfile_yaml) for f in args.bcfiles ]

    return res

def check_exists(f, syntax_check=True):
    """Check that a file exists. In fact, check it's valid YAML
    """
    if syntax_check:
        load_yaml(f)
    else:
        assert os.path.exists(f)

    return '@' + f

def parse_args(*args):
    description = """Provide XML for the various bits of report.
                  """
    argparser = ArgumentParser( description=description,
                                formatter_class = ArgumentDefaultsHelpFormatter )
    argparser.add_argument("bcfiles", nargs='*',
                            help="Info YAML files to be linked per barcode")
    argparser.add_argument("--sc_data",
                            help="Location of sc_data.yaml for the cell")
    argparser.add_argument("--unassigned",
                            help="Location of info.yaml for unassigned reads")

    argparser.add_argument("--raw_data_report",
                            help="Location of raw_data.report.json for this cell")
    argparser.add_argument("--adapter_report",
                            help="Location of adapter.report.json for this cell")
    argparser.add_argument("--ccs_report",
                            help="Location of ccs.report.json for this cell")
    argparser.add_argument("--control_report",
                            help="Location of control.report.json for this cell")
    argparser.add_argument("--loading_report",
                            help="Location of loading.report.json for this cell")

    argparser.add_argument("-d", "--debug", action="store_true",
                            help="Print more verbose debugging messages.")
    argparser.add_argument("-c", "--check_yaml", action="store_true",
                            help="Check that the YAML files can be loaded.")
    argparser.add_argument("-x", "--extract_ids", action="store_true",
                            help="Add the run_id, cell_id, cell_uuid, ws_name from the info files")

    return argparser.parse_args(*args)


if __name__ == "__main__":
    main(parse_args())
