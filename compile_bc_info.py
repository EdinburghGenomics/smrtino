#!/usr/bin/env python3
import os, sys
import logging as L
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
import yaml

from smrtino.ParseXML import get_readset_info, get_runmetadata_info

""" Emits .info.yaml files for SMRT cells by parsing the xml files from
    SMRT link, among other things. This script, along with make_report.py,
    essentially links Snakefile.process_cells and Snakefile.report by taking
    the info we get from the former and compiling it under the direction of
    the latter.

    This Revio version is to be used per-barcode, and the multiple files
    are later combined to get the full cell info.
"""

def main(args):

    L.basicConfig(level=(L.DEBUG if args.debug else L.WARNING), stream=sys.stderr)

    info = gen_info(args)

    print(yaml.safe_dump(info, default_flow_style=False), end='')

def gen_info(args):
    # Start with the consensusreadset.xml file
    xmlfile, = args.xmlfile

    # Load the file then...
    L.debug(f"Reading from {xmlfile}")
    info = get_readset_info(xmlfile)
    if args.runxml:
        L.debug(f"Also reading from {args.runxml}")
        info['_run'] = get_runmetadata_info(args.runxml)

    info['_filename'] = os.path.basename(xmlfile)

    # Add plots if we have them
    for p in args.plots or []:
        with open(p) as yfh:
            info.setdefault('_plots', []).append(yaml.safe_load(yfh))

    # Add taxon if supplied
    for t in args.taxon or []:
        with open(t) as tfh:
            info['guessed_taxon'] = tfh.read().strip()

    # Add stats if we have them
    for s in args.stats or []:
        filename = '-'
        if s.endswith(".cstats.yaml"):
            filename = s.split('.')[-3].capitalize()

        with open(s) as sfh:
            stats = yaml.safe_load(sfh)
            stats['File'] = filename
            stats['_headings'] = ['File'] + stats['_headings']
            info.setdefault('_cstats', []).append(stats)

    # Return the info dictionary
    return info

def parse_args(*args):
    description = """ Provide an XML file to digest. YAML will be printed on
                      stdout.
                  """
    argparser = ArgumentParser( description=description,
                                formatter_class = ArgumentDefaultsHelpFormatter )
    argparser.add_argument("xmlfile", nargs=1,
                            help="Readset XML to be loaded")
    argparser.add_argument("-r", "--runxml", nargs="?",
                            help="Optional run.metadata XML to be loaded")
    argparser.add_argument("-p", "--plots", nargs="*",
                            help="Plots generated for this barcode (YAML files)")
    argparser.add_argument("-s", "--stats", nargs="*",
                            help="Stats generated for this barcode (YAML files)")
    argparser.add_argument("-t", "--taxon", nargs="*",
                            help="BLAST taxon guess for this barcode (text file)")
    argparser.add_argument("-d", "--debug", action="store_true",
                            help="Print more verbose debugging messages.")

    return argparser.parse_args(*args)


if __name__ == "__main__":
    main(parse_args())