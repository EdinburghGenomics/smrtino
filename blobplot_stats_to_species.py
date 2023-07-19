#!/usr/bin/env python3

""" Use some dirty heuristics to look at the summary tables from
    Blobtools and decide what species is in the sample.
"""

from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
import logging as L
from pprint import pprint

def main(args):
    L.basicConfig(level=(L.DEBUG if args.verbose else L.WARNING))

    # We could use Pandas here, but I'm not going to. Just load the TSV files
    # naively.
    stats_tables = []
    for statfile in args.stats:
        stats_tables.append(load_stat_file(statfile))

    verdict = tables_to_verdict(stats_tables, args.cutoff, args.dominance)

    print(";".join(verdict or [f"No hits >{args.cutoff}%"]))

def tables_to_verdict(stats_tables, cutoff, dominance):

    ignore_names = set(["all", "no-hit", "other", "synthetic construct"])
    verdict = []

    for table in stats_tables:
        lastperc = 0.0
        for arow in table:
            # Get the taxon name and the hit percentage
            tname, tperc = arow['name'], arow['_sortkey']
            if tperc < cutoff:
                # We're not interested in this or anything below it.
                # Go to next table.
                break
            elif tname in ignore_names:
                # We don't care about this row but keep looking
                continue
            elif ( tperc >= cutoff
                   and tperc >= (lastperc - dominance) ):
                verdict.append(f"{tname} ({tperc}%)")
                lastperc = tperc

        # If we already have a verdict, no need to go to the next table
        if verdict:
            break

    return verdict


def load_stat_file(filename, sortby="cov0_read_map_p"):
    """Load the TSV file. We only need the first and last columns but may as well get
       the lot.
    """
    lines = []
    with open(filename) as fh:

        for aline in fh:
            aline = aline.strip()
            if aline.startswith("# "):
                headers = aline[2:].split("\t")
                break
            assert aline.startswith("##")

        for aline in fh:
            linedict = dict(zip( headers,
                                 aline.strip().split("\t") ))

            linedict['_sortkey'] = float(linedict[sortby].strip("% "))

            lines.append(linedict)

    lines.sort(key=lambda r: float(r['_sortkey']), reverse=True)

    return lines

def parse_args(*args):
    description = """ Takes a list of blobplot.stats.txt tables from blobtools
                      and tells you what the organism being sequenced is, using
                      dirty heuristics.
                  """
    argparser = ArgumentParser( description=description,
                                formatter_class = ArgumentDefaultsHelpFormatter )
    argparser.add_argument("stats", nargs='+',
                            help="The blobplot.stats.txt files to read.")
    argparser.add_argument("-c", "--cutoff", type=float, default=10.0,
                            help="Minimal percentage to consider.")
    argparser.add_argument("-d", "--dominance", type=float, default=20.0,
                            help="Minimal percentage difference for secondary hit to be ignored.")
    argparser.add_argument("-v", "--verbose", "--debug", action="store_true",
                            help="Print more verbose debugging messages.")

    return argparser.parse_args(*args)

if __name__ == "__main__":
    main(parse_args())
