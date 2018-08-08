#!/usr/bin/env python3
import os, sys, re
import logging as L
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
import xml.etree.ElementTree as ET
import yaml

""" Emits .info.yml files for SMRT cells by parsing the xml files from
    SMRT link, among other things. This script, along with make_report.py,
    essentially links Snakefile.process_cells and Snakefile.report by taking
    the info we get from the former and compiling it under the direction of
    the latter.
"""
_ns = dict( pbmeta = 'http://pacificbiosciences.com/PacBioCollectionMetadata.xsd',
            pb     = 'http://pacificbiosciences.com/PacBioDatasets.xsd' )

def main(args):

    L.basicConfig(level=(L.DEBUG if args.debug else L.WARNING), stream=sys.stderr)

    # Load the file then...
    xmlfile, = args.xmlfile
    L.debug("Reading from {}".format(xmlfile))
    root = ET.parse(xmlfile).getroot()

    info = get_the_info(root)

    info['_filename']= xmlfile

    # Print the result
    print(yaml.safe_dump(info, default_flow_style=False))

def get_the_info(root):
    """ Glean info from the file as per scan_for_smrt_cells in get_pacbio_yml.py
    """
    rf = root.find('.//pbmeta:ResultsFolder', _ns).text.rstrip('/')
    cmd = root.find('.//pbmeta:CollectionMetadata', _ns)

    info = { 'run_id': rf.split('/')[-2],
             'run_slot': rf.split('/')[-1], # Also could get this from TimeStampedName
             'cell_id': cmd.attrib.get('Context') }

    well_samples = root.findall('.//pbmeta:WellSample', _ns)
    # There should be 1!
    L.debug("Found {} WellSample records".format(len(well_samples)))

    if len(well_samples) == 1:
        ws, = well_samples

        info['ws_name'] = ws.attrib.get('Name', '')
        info['ws_desc'] = ws.attrib.get('Description', '')

        mo = re.match('\d+', info['ws_name'])
        if mo:
            info['ws_project'] = mo.group(0)

    return info

def parse_args(*args):
    description = """ Provide an XML file to digest. YAML will be printed on
                      stdout.
                  """
    argparser = ArgumentParser( description=description,
                                formatter_class = ArgumentDefaultsHelpFormatter )
    argparser.add_argument("xmlfile", nargs=1,
                            help="XML to be loaded")
    argparser.add_argument("-d", "--debug", action="store_true",
                            help="Print more verbose debugging messages.")

    return argparser.parse_args(*args)


if __name__ == "__main__":
    main(parse_args())
