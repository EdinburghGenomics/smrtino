#!/usr/bin/env python3
import os, sys
import logging as L
from pprint import pprint
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter

from smrtino.ParseXML import get_readset_info, get_metadata_info
from smrtino import load_yaml, dump_yaml, squash_barcode

""" Emits .info.yaml files for SMRT cells by parsing the xml files from
    SMRT link, among other things. This script, along with make_report.py,
    essentially links Snakefile.process_cells and Snakefile.report by taking
    the info we get from the former and compiling it into a PanDoc report
    under the direction of the latter.

    This Revio version is to be used per-barcode, and the multiple files
    are later combined to get the full cell info.
"""

def main(args):

    L.basicConfig(level=(L.DEBUG if args.debug else L.WARNING), stream=sys.stderr)

    info = gen_info(args)

    dump_yaml(info, fh=sys.stdout)

def gen_info(args):
    # Start with the consensusreadset.xml file
    xmlfile, = args.xmlfile

    # Load the readset.xml file then...
    L.debug(f"Reading from {xmlfile}")
    info = get_readset_info(xmlfile)
    if args.metaxml:
        # The cell metadata.xml file has some useful run info
        L.debug(f"Also reading from {args.metaxml}")
        rmd = get_metadata_info(args.metaxml)
        info['_run'] = rmd

    info['_filename'] = os.path.basename(xmlfile)

    # We used to get the barcode from the file name, but now it comes
    # from get_readset_info()

    # check that info now has bs_name as well as ws_name (in case I'm reading an
    # old YAML file)
    assert ('bs_name' in info) and ('ws_name' in info)

    # Add plots if we have them
    for p in args.plots or []:
        info.setdefault('_plots', []).append(load_yaml(p, dictify_result=True))

    # Add taxon if supplied
    # The reason for passing the file name and not the value is because in Snakemake
    # it's fiddly to deal with the if/else whether there is a taxon guess or not, but
    # here it's easy.
    if args.taxon:
        with open(args.taxon) as tfh:
            info['guessed_taxon'] = tfh.read().strip()

    # Add binning info too
    if args.binning:
        with open(args.binning) as bfh:
            info['quality_binning'] = bfh.read().strip().capitalize()

    # And we want to know if this is Kinnex or not
    if args.kinnex:
        info['kinnex_type'] = load_yaml(args.kinnex)['mas']

    # Add stats if we have them
    for s in args.stats or []:
        s_split = os.path.basename(s).split(".")
        hifi_or_fail = barcode = mas = "-"
        if s_split[0] == info['cell_id'] and s.endswith(".cstats.yaml"):
            s_split = s_split[1:-2]

            # Here we do have to get info from the file names
            hifi_or_fail = s_split[0].capitalize()
            barcode = s_split[1]
            if len(s_split) == 3:
                mas = s_split[2]

        stats = load_yaml(s, dictify_result=True)
        stats['Barcode'] = squash_barcode(barcode)
        stats['File'] = hifi_or_fail
        stats['Kinnex'] = mas
        stats['_headings'] = ['Barcode', 'File', 'Kinnex'] + stats['_headings']
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
    argparser.add_argument("-m", "--metaxml", nargs="?",
                            help="Optional metadata XML to be loaded for run info")
    argparser.add_argument("-p", "--plots", nargs="*",
                            help="Plots generated for this barcode (YAML files)")
    argparser.add_argument("-s", "--stats", nargs="*",
                            help="Stats generated for this barcode (YAML files)")
    argparser.add_argument("-t", "--taxon",
                            help="BLAST taxon guess for this barcode (text file)")
    argparser.add_argument("-b", "--binning",
                            help="Whether quality scores are binned or unbinned (text file)")
    argparser.add_argument("-k", "--kinnex",
                            help="The kinnex_scan.yaml file for this barcode")
    argparser.add_argument("-d", "--debug", action="store_true",
                            help="Print more verbose debugging messages.")

    return argparser.parse_args(*args)


if __name__ == "__main__":
    main(parse_args())
