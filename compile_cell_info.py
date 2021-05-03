#!/usr/bin/env python3
import os, sys
import logging as L
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
import yaml

from smrtino.ParseXML import get_readset_info

""" Emits .info.yml files for SMRT cells by parsing the xml files from
    SMRT link, among other things. This script, along with make_report.py,
    essentially links Snakefile.process_cells and Snakefile.report by taking
    the info we get from the former and compiling it under the direction of
    the latter.
"""

def main(args):

    L.basicConfig(level=(L.DEBUG if args.debug else L.WARNING), stream=sys.stderr)

    # If a filter was applied then we actually want to look at the unfiltered version
    # Splitting paths is always fiddly...
    pbits = args.xmlfile[0].split('/')
    fbits = pbits[-1].split('.')
    if len(fbits) == 4:
        L.debug("File was filtered. Loading unfiltered version.")
        filtername = fbits[1]
        pbits[-1] = '{}.{}.{}'.format( fbits[0], *fbits[2:] )
    else:
        filtername = None
    # Reconstruct path...
    xmlfile = '/'.join(pbits)

    # The penultimate part of the filename should be 'consensusreadset' or 'subreadset' but we'll
    # get this info from the XML instead.

    # Load the file then...
    L.debug("Reading from {}".format(xmlfile))
    info = get_readset_info(xmlfile)

    info['filter_added'] = filtername
    info['_filename'] = xmlfile

    # Add plots if we have them
    for p in args.plots or []:
        with open(p) as yfh:
            info.setdefault('_plots', []).append(yaml.safe_load(yfh))

    # Add stats if we have them
    for s in args.stats or []:
        filename = '-'
        if s.endswith(".cstats.yml"):
            filename = s.split('.')[-3].capitalize()

        with open(s) as sfh:
            stats = yaml.safe_load(sfh)
            stats['File'] = filename
            stats['_headings'] = ['File'] + stats['_headings']
            info.setdefault('_cstats', []).append(stats)

    # Print the result
    print(yaml.safe_dump(info, default_flow_style=False))

def parse_args(*args):
    description = """ Provide an XML file to digest. YAML will be printed on
                      stdout.
                  """
    argparser = ArgumentParser( description=description,
                                formatter_class = ArgumentDefaultsHelpFormatter )
    argparser.add_argument("xmlfile", nargs=1,
                            help="XML to be loaded")
    argparser.add_argument("-p", "--plots", nargs="*",
                            help="Plots generated for this cell (YAML files)")
    argparser.add_argument("-s", "--stats", nargs="*",
                            help="Stats generated for this cell (YAML files)")
    argparser.add_argument("-d", "--debug", action="store_true",
                            help="Print more verbose debugging messages.")

    return argparser.parse_args(*args)


if __name__ == "__main__":
    main(parse_args())
