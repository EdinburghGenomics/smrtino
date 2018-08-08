#!/usr/bin/env python3
import os, sys, re
import logging as L
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
import xml.etree.ElementTree as ET

""" Emits .info.yml files for SMRT cells by parsing the xml files from
    SMRT link, among other things. This script, along with make_report.py,
    essentially links Snakefile.process_cells and Snakefile.report by taking
    the info we get from the former and compiling it under the direction of
    the latter.
"""
_ns = dict( pbmeta = 'http://pacificbiosciences.com/PacBioCollectionMetadata.xsd' )

def main(args):

    L.basicConfig(level=(L.DEBUG if args.debug else L.WARNING))

    # Load the file then...
    root = ET.parse(args.xmlfile).getroot()

    # 
        filter_was_done = bool(root.findall('.//pbmeta:ControlKit', ns))

def parse_args(*args):
    description = """ Provide an XML file to digest. YAML will be printed on
                      stdout.
                  """
    argparser = ArgumentParser( description=description,
                                formatter_class = ArgumentDefaultsHelpFormatter )
    argparser.add_argument("xmlfile", nargs=1,
                            help="XML to be loaded")
    argparser.add_argument("-d", "--debug", action="set_true",
                            help="Print more verbose debugging messages.")

    return argparser.parse_args(*args)


if __name__ == "__main__":
    main(parse_args())
