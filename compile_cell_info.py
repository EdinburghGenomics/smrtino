#!/usr/bin/env python3
import os, sys
import logging as L
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter

from zipfile import ZipFile
from smrtino import load_yaml, dump_yaml
from smrtino.ParseXML import get_metadata_info2
import json
from pprint import pprint

""" The info needed to report on a SMRT cell consists of several YAML files:
        sc_data.yaml about the files in the upstream
        unassigned.yaml about the unassigned reads (if applicable)
        bc1.yaml bc2.yaml about the barcodes.

    This super-simple script just outputs a file linking to these other files.
"""

REPORTS_IN_ZIP = "raw_data adapter ccs control loading".split()

def main(args):

    L.basicConfig(level=(L.DEBUG if args.debug else L.WARNING), stream=sys.stderr)

    # Load the JSON files from reports.zip
    json_reports = load_reports_zip(vars(args))

    # Info from metadata.xml gets folded into these reports.
    if args.metaxml:
        metadata_xml_info = get_metadata_info2(args.metaxml)
    else:
        metadata_xml_info = None

    # Build the links to the files.
    info = gen_info(args)

    if args.extract_ids:
        if json_reports:
            exit("FIXME - There's no point in using -x if we are loading metadata.xml directly.")
        info.update(extract_ids_multi(args.bcfiles))

    if json_reports:
        info.update(compile_json_reports(json_reports, metadata_xml_info))

    dump_yaml(info, fh=sys.stdout)

def load_reports_zip(args_dict):
    """Load the various JSON files directly from reports.zip. If any --foo_report
       is specified that takes precedence.
       Pass args as a dict to make testing this function a tad easier.
    """
    res = {}
    if args_dict.get('reports_zip'):
        with ZipFile(args_dict['reports_zip']) as repzip:
            for r in REPORTS_IN_ZIP:
                json_file = f"{r}.report.json"
                try:
                    with repzip.open(json_file) as jfh:
                        res[r] = json.load(jfh)
                except KeyError:
                    L.warning(f"{json_file} was not found in {args_dict['reports_zip']}")

    # Now the individual files, if any
    for r in REPORTS_IN_ZIP:
        if args_dict.get(f'{r}_report'):
            with open(args_dict[f'{r}_report']) as jfh:
                if r in res:
                    L.warning(f"Overiding {r}.report.json from {args_dict['reports_zip']}"
                              f" with {args_dict[f'{r}_report']}")
                res[r] = json.load(jfh)

    pprint(res)
    return res

def compile_json_reports(reports_dict):

    res = dict(reports = {})

    return res

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

    argparser.add_argument("--reports_zip",
                            help="Location of reports.zip for this cell")
    for r in REPORTS_IN_ZIP:
        argparser.add_argument(f"--{r}_report",
                                help=f"Location of {r}.report.json for this cell")

    argparser.add_argument("--metaxml",
                            help="Location of metadata.xml for this cell")

    argparser.add_argument("-d", "--debug", action="store_true",
                            help="Print more verbose debugging messages.")
    argparser.add_argument("-c", "--check_yaml", action="store_true",
                            help="Check that the YAML files can be loaded.")
    argparser.add_argument("-x", "--extract_ids", action="store_true",
                            help="Add the run_id, cell_id, cell_uuid, ws_name from the info files")

    return argparser.parse_args(*args)


if __name__ == "__main__":
    main(parse_args())
