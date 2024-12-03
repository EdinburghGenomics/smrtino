#!/usr/bin/env python3
"""Getting the sample setup info from SMRTLink is much more of a faff than it
   should be. But we can do it.
"""

import os, sys, re
import logging as L
import json
import xml.etree.ElementTree as ET
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter

from smrtino.SMRTLink import SMRTLinkClient
from smrtino import load_yaml, dump_yaml

conn = None

def main(args):
    L.basicConfig(level=(L.DEBUG if args.debug else L.WARNING))

    # Load that YAML file
    info_yaml = None
    if args.ws_name:
        ws_name = args.ws_name
    elif args.info_yaml:
        info_yaml = load_yaml(args.info_yaml)
        ws_name = info_yaml['ws_name']

    # Load the options
    options_yaml = dict()
    if args.options:
        try:
            cell_id = info_yaml['cell_id']
            options_yaml = load_yaml(args.options).get(cell_id) or dict()

        except FileNotFoundError:
            L.info(f"Skipping missing options file {args.options}")

    # Decide how we want to exit
    if not args.errors_to_yaml:
        exit = sys.exit
    else:
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

    if options_yaml.get('smrtlink_sample_uuid'):
        smrtlink_sample_uuid = options_yaml['smrtlink_sample_uuid']
    else:
        L.debug("Getting the sample list from the API")

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

        smrtlink_sample_uuid = matching_samples[-1]['uniqueId']

    # Now we have to re-fetch to get the finalHtml which holds the "Sample Concentration (nM)"
    sample_record = conn.get_endpoint(f"/smrt-link/samples/{smrtlink_sample_uuid}")

    # The 'details' is an embedded jSON string. Of course it is.
    sample_record['details'] = json.loads(sample_record['details'])

    # And in a final piece of silliness, extract the "Sample Concentration (nM)" and
    # "Sample Volume to Use" the finalHtml text.
    sample_details_table = scrape_sample_details_table(sample_record['finalHtml'])
    sample_record['details']['Sample Concentration (nM)'] = (
            scrape_sample_conc_nm(sample_details_table) )
    sample_record['details']['Sample Volume to Use'] = (
            scrape_volume_to_use(sample_details_table) )

    # And we can now get rid of sample_record['finalHtml']
    del sample_record['finalHtml']

    # Make 'Insert_Size' be an int. Ditto 'On_Plate_Loading_Concentration'
    for k in ['Insert_Size', 'On_Plate_Loading_Concentration']:
        sample_record['details'][k] = int(sample_record['details'][k])

    if info_yaml is not None and 'reports' in info_yaml:
        cross_check_info(info_yaml['reports'], sample_record['details'])

    # Shall we dump this as YAML or JSON? Other things are YAML, so stick with that.
    dump_yaml(sample_record, fh=sys.stdout)

def cross_check_info(reports_dict, deets_dict):
    """Sanity check that the info we have already does match the sample.
    """
    # Check the insert size we got from metadata.xml (in sl_dict) versus the one we
    # see in sample-setup.yaml (sample_dict)
    sl_dict = reports_dict['Sample Loaded']
    if sl_dict['Insert size (bp)'] != deets_dict['Insert_Size']:
        raise RuntimeError("Value mismatch in Insert Size")

    # Also check loading conc while we are at it
    loading_dict = reports_dict['Loading']
    if ( loading_dict['OPLC (pM), On-Plate Loading Conc.'] !=
         deets_dict['On_Plate_Loading_Concentration'] ):
        raise RuntimeError("Value mismatch in On-Plate Loading Conc")

    # And the Application
    run_dict = reports_dict['Run']
    if run_dict['Library type'] != deets_dict['Application']:
        raise RuntimeError("Value mismatch in Application")

def scrape_sample_details_table(html_text):

    # The HTML is actually XHTML so we can do this...
    root = ET.fromstring(html_text)
    deets_table = root.find(".//table[@class='SampleDetailsTable SampleDetailsTableHT']")
    deets_rows = [ r.findall('td') for r in deets_table.findall('tbody/tr') ]

    return deets_rows

def scrape_sample_conc_nm(deets_rows):
    # This should get a single pair of elements
    conc_row, = [ r for r in deets_rows if r[0].text.strip() == "Sample Concentration" ]

    # Now yank the second bit of text
    conc_text = list(conc_row[1].itertext())[1]

    # And split off the nM from the end
    return re.fullmatch(r'([0-9.]+) nM', conc_text).group(1)

def scrape_volume_to_use(deets_rows):

    vol_row, = [ r for r in deets_rows if r[0].text.strip() == "Sample Volume to Use" ]

    vol_text = vol_row[1].text.strip()

    # And split off the µL from the end
    return re.fullmatch(r'([0-9.]+) .L', vol_text).group(1)

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
    argparser.add_argument("-o", "--options",
                           help="Read this file for extra options/overrides. If the file is"
                                " not present the script will just regard it as empty")

    argparser.add_argument("-d", "--debug", action="store_true",
                            help="Print more verbose debugging messages.")

    parsed_args = argparser.parse_args(*args)

    if not(parsed_args.info_yaml) and parsed_args.options:
        # Because we need to get the cell id to find the right section in the options file
        exit("Setting an options file only works with the .info.yaml argument")

    if not(parsed_args.info_yaml or parsed_args.ws_name):
        argparser.print_help()
        exit(2)
    if parsed_args.info_yaml and parsed_args.ws_name:
        exit("Please give either --ws_name or specify a .info.yaml file but not both")

    return parsed_args

if __name__ == "__main__":
    main(parse_args())
