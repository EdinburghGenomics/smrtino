#!/usr/bin/env python3

import os, sys, re
import logging as L
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter

import json
import yaml

ALLOWED_MAS = [8, 12, 16]

def main(args):
    """Main function
    """
    reads_per_total = args.total
    reads_per_json = None
    if args.json is not None:
        L.debug("Loading JSON file to get reads_per_json")
        reads_per_json = get_reads_from_json(args.json)
    else:
        L.info(f"No JSON file provided. Assuming total ({args.total}) is accurate.")
        reads_per_json = reads_per_total

    if reads_per_total is None:
        L.info(f"No total provided. Assuming total is as per {args.json}: {reads_per_json})")
        reads_per_total = reads_per_json

    assert reads_per_total is not None
    assert reads_per_json is not None

    # See if we cannot judge at all
    if reads_per_total == 0 or reads_per_json < reads_per_total:
        return show_result(mas=None, reason="sample too small")

    # See if we have more reads than expected somehow. Make this an error
    if reads_per_json > reads_per_total:
        return show_result(mas=None, reason="sample size mismatch")

    # OK, now decide on a cutoff and load the .ligations.csv
    reads_cutoff = make_cutoff(reads_per_total)

    ligations_csv, = args.ligations_csv
    with open(ligations_csv) as fh:
        ligations = count_ligations(fh, cutoff=reads_cutoff, check=max(ALLOWED_MAS))

        if ligations == 0:
            show_result(mas=None, reason=f"no significant ligations found")
        elif ligations in ALLOWED_MAS:
            show_result(mas=f"mas{ligations}", sampled=reads_per_total)
        else:
            show_result(mas=None, reason=f"unexpected number of ligation junctions seen: {ligations}")

def show_result(mas, **kwargs):
    """Just print YAML to STDOUT
    """
    yaml.safe_dump(dict(mas=mas, **kwargs), sys.stdout)

def count_ligations(fh, cutoff, check=None):
    """Scan the lines in the ligations.csv file and count the lines where
       the last column >= cutoff

       If check is set, will raise a RuntimeError if the number of junctions
       is wrong.
    """
    res = 0
    header = next(fh).strip()
    if not header == "adapter_1,adapter_2,ligations":
        raise RuntimeError(f"Unexpected CSV header: {header}")
    for l in fh:
        adapter_1, adapter_2, ligations = l.strip().split(",")
        if int(ligations) >= cutoff:
            res += 1

    if check:
        if not (adapter_1 == adapter_2 and int(adapter_1) == check):
            raise RuntimeError(f"Unexpected last adapter: {adapter_1},{adapter_2}")

    return res

def make_cutoff(total, percent=50):
    """If the total sampled is 1000, then anything > 500 is a detection.
       But we do want to deal with corner cases, and consider that we might
       want to tweak the percentage.
    """
    res = (total * percent) // 100

    # For tiny numbers, fix it.
    if res == 0 and percent > 0:
        res = 1

    return res

def get_reads_from_json(jfile):
    with open(jfile) as fh:
        j = json.load(fh)

    reads_attr, = [ a for a in j['attributes'] if a['id'] == "reads" ]
    return reads_attr['value']

def setup_logging(debug):
    L.basicConfig(level = L.DEBUG if debug else L.INFO)

def parse_args():

    description = "Check output of Skera to heuristically determine the type of Mas-Seq used"

    parser = ArgumentParser( description = description,
                             formatter_class = ArgumentDefaultsHelpFormatter)

    parser.add_argument("-t", "--total", type=int,
                        help="total number of reads expected")
    parser.add_argument("-j", "--json",
                        help="JSON file containing .summary.json from skera")
    parser.add_argument("ligations_csv", nargs=1,
                        help="CSV file containing .ligations.csv from skera")
    parser.add_argument("--debug", "--verbose", dest="debug", action="store_true", default=False,
                        help="show debugging information")
    parser.add_argument("--version", action="version", version="0.0.0")

    args = parser.parse_args()

    if args.total is None and args.json is None:
        exit("You need to provide either a total (-t) or a JSON file (-j), preferably both.")

    return args

if __name__ == '__main__':
    args = parse_args()
    setup_logging(args.debug)
    main(args)
