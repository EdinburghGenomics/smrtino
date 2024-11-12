#!/usr/bin/env python3
"""Getting the sample setup info from SMRTLink is much more of a faff than it
   should be. But we can do it.
"""

import os, sys
import logging as L
import json
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter

from smrtino.SMRTLink import SMRTLinkClient
from smrtino import load_yaml, dump_yaml

conn = None

def main(args):
    L.basicConfig(level=(L.DEBUG if args.debug else L.WARNING))

    # Load that YAML file
    if args.ws_name:
        ws_name = args.ws_name
    elif args.info_yaml:
        info_yaml = load_yaml(args.info_yaml)
        ws_name = info_yaml['ws_name']

    # Decide how we want to exit
    exit = sys.exit
    if args.errors_to_yaml:
        def exit(msg):
            """Alternative exit()
            """
            dump_yaml({"_error": msg}, fh=sys.stdout)
            sys.exit(0)

    L.debug(f"ws_name is {ws_name}")

    if args.rc_section == 'none':
        L.warning("Running in no-connection mode as rc_section==none")
        # Test mode!
        # TODO
        return

    # Simplest connection with ~/.smrtlinkrc defaults
    global conn
    conn = SMRTLinkClient.connect_with_creds(section=args.rc_section)

    L.debug("Getting the sample list form the API")

    # This is dumb. The UUIDs are broken so we need to fetch all the samples and look for a
    # match by name. SRSLY.
    # At the time of writing, multiple samples have multiple entries. "30940GK0002L01" is
    # a case in point, being just from October 2024.
    # We should sanity check that the On_Plate_Loading_Concentration and Insert_Size matches
    # what we have in the metadata.xml when this info is used.
    all_samples = conn.get_endpoint("/smrt-link/samples")
    matching_samples = [s for s in all_samples if s['name'] == ws_name]

    if not(matching_samples):
        exit(f"Sample {ws_name} was not found in the API")

    if len(matching_samples) > 1:
        if not args.use_latest:
            exit(f"Multiple samples have the name {ws_name}.")
        else:
            L.warning(f"Using the last of {len(matching_samples)} samples with the name {ws_name}.")

    # Finally
    sample_record = matching_samples[-1]

    # And in a final piece of silliness, the 'details' is an embedded jSON string
    sample_record['details'] = json.loads(sample_record['details'])

    # Shall we dump this as YAML or JSON? Other things are YAML, so stick with that.
    dump_yaml(sample_record, fh=sys.stdout)

def parse_args(*args):
    description = """Takes a .info.yaml file (or just a ws_name) and fetches the sample
                     setup info from SMRTLink.

                     Connection to the API is as per ~/.smrtlinkrc - note that the
                     pbicsuser does not have the permission to run this.
                  """
    argparser = ArgumentParser( description=description,
                                formatter_class = ArgumentDefaultsHelpFormatter )
    argparser.add_argument("--rc_section", default=os.environ.get("SMRTLINKRC_SECTION", "smrtlink"),
                            help="Read specified section in .smrtlinkrc for connection details")

    argparser.add_argument("--ws_name",
                           help="Directly provide the ws_name rather than reading it from"
                                " the .info.yaml")
    argparser.add_argument("info_yaml", nargs="?",
                           help=".info.yaml file produced by compile_cell_info.py")
    argparser.add_argument("--use_latest", action="store_true",
                            help="Use the latest sample if the name is ambiguous.")
    argparser.add_argument("--errors_to_yaml", action="store_true",
                            help="Add the errors into the JSON. Allows Snakemake to continue.")

    argparser.add_argument("-d", "--debug", action="store_true",
                            help="Print more verbose debugging messages.")

    parsed_args = argparser.parse_args(*args)

    if not(parsed_args.info_yaml or parsed_args.ws_name):
        argparser.print_help()
        exit(2)
    if parsed_args.info_yaml and parsed_args.ws_name:
        exit("Please give either --ws_name or specify a .info.yaml file but not both")

    return parsed_args

if __name__ == "__main__":
    main(parse_args())
