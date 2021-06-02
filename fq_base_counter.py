#!/usr/bin/env python3

import os, sys, re
import gzip
import json
import collections
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter

""" This tool counts up the reads and bases in a FASTQ file.
    The idea is that for each .fastq.gz, as well as the .md5 file we also
    want a .fastq.count which has:

     total_reads: ...
     read_length: ...
     total_bases: ...
     non_n_bases: ...

    The script takes a .fastq.gz file to examine.

    This version of the scrip does not attempt to look for an index sequence.
"""

def parse_args():

    description = "Output base counts on a FASTQ file."

    parser = ArgumentParser( description = description,
                             formatter_class = ArgumentDefaultsHelpFormatter)

    parser.add_argument("infile", nargs='+',
                        help=".fastq.gz file to be read")

    return parser.parse_args()

def main(args):

    for fn in args.infile:
        print_info(scan_fq(fn), fn=os.path.basename(fn))

def scan_fq(filename):
    """ Read a file. The file must actually be a gzipped file, unless it's completely empty,
        which is useful for testing.
    """
    lens_found = collections.Counter()
    ns_found = 0

    if os.stat(filename).st_size == 0:
        return dict( total_reads = 0,
                     min_read_len = 0,
                     max_read_len = 0,
                     n_bases = 0       )

    try:
        n = 0
        with gzip.open(filename, mode='rb') as fh:
            for n, l in enumerate(fh):
                if n % 4 == 1:
                    # Sequence line
                    lens_found[len(l) - 1] += 1
                    ns_found += l.count(b'N')
    except OSError as e:
        #The GZip module doesn't tell you what file it was trying to read
        e.filename = filename
        e.strerror = e.args[0]
        raise

    return dict( total_reads = (n + 1) // 4,
                 min_read_len = min(lens_found.keys() or [0]),
                 max_read_len = max(lens_found.keys() or [0]),
                 total_bases = sum([ l * c for l, c in lens_found.items()]),
                 n_bases = ns_found )

def print_info(fq_info, fn='input.fastq.gz'):
    """ Show what we got.
    """

    print( "filename:    {}".format(fn) )

    print( "total_reads: {}".format(fq_info['total_reads']) )

    if fq_info['min_read_len'] == fq_info['max_read_len']:
        total_bases = fq_info['min_read_len'] * fq_info['total_reads']

        print( "read_length: {}".format(fq_info['min_read_len']) )
    else:
        # This must have been counted directly
        total_bases = fq_info['total_bases']

        print( "read_length: {}-{}".format(fq_info['min_read_len'], fq_info['max_read_len']) )

    print( "total_bases: {}".format(total_bases) )

    if 'n_bases' in fq_info:
        print( "non_n_bases: {}".format(total_bases - fq_info['n_bases']) )

    if 'q30_bases' in fq_info:
        print( "q30_bases:   {}".format(fq_info['q30_bases']) )

if __name__ == '__main__':
    main(parse_args())
