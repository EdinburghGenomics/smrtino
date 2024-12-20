#!/usr/bin/env python3

import os, sys, re
import gzip
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

    parser.add_argument("-s", "--stdin", action="store_true",
                        help="actually read from stdin, but using the given filename")
    parser.add_argument("-c", "--cstats",
                        help="actually get the numbers from cstats.yaml, but using the given filename")

    parser.add_argument("infile", nargs=1,
                        help=".fastq.gz file to be read")

    return parser.parse_args()

def main(args):

    fn, = args.infile

    if args.cstats:
        # Short-circuit the file reading. Needs newer cstats with the extra infos
        print_info(load_cstats(args.cstats), fn=os.path.basename(fn))
    elif args.stdin:
        print_info(scan_fh(sys.stdin.buffer), fn=os.path.basename(fn))
    else:
        print_info(scan_fq(fn), fn=os.path.basename(fn))

def load_cstats(filename):
    import yaml

    with open(filename) as yfh:
        ydata = yaml.safe_load(yfh)

    return dict( total_reads = ydata['Reads'],
                 min_read_len = ydata['Min read length'] if ydata['Reads'] else 0,
                 max_read_len = ydata['Max read length'] if ydata['Reads'] else 0,
                 total_bases = ydata['Total bases'],
                 non_n_bases = ydata['non-N bases'] if ydata['Reads'] else 0, )

def scan_fh(filehandle):
    """ Read an open file handle. The data must be uncompressed.
    """
    lens_found = collections.Counter()
    ns_found = 0
    n = 0

    for n, l in enumerate(filehandle):
        if n % 4 == 1:
            # Sequence line
            lens_found[len(l) - 1] += 1
            ns_found += l.count(b'N')

    return dict( total_reads = (n + 1) // 4,
                 min_read_len = min(lens_found.keys() or [0]),
                 max_read_len = max(lens_found.keys() or [0]),
                 total_bases = sum([ l * c for l, c in lens_found.items()]),
                 n_bases = ns_found )

def scan_fq(filename):
    """ Read a file. The file must actually be a gzipped file, unless it's completely empty,
        which is useful for testing.
    """
    if os.stat(filename).st_size == 0:
        return dict( total_reads = 0,
                     min_read_len = 0,
                     max_read_len = 0,
                     n_bases = 0       )

    try:
        with gzip.open(filename, mode='rb') as fh:
            return scan_fh(fh)
    except OSError as e:
        #The GZip module doesn't tell you what file it was trying to read
        e.filename = filename
        e.strerror = e.args[0]
        raise

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

    if 'non_n_bases' in fq_info:
        print( "non_n_bases: {}".format(fq_info['non_n_bases']) )
    elif 'n_bases' in fq_info:
        print( "non_n_bases: {}".format(total_bases - fq_info['n_bases']) )

    if 'q30_bases' in fq_info:
        print( "q30_bases:   {}".format(fq_info['q30_bases']) )

if __name__ == '__main__':
    main(parse_args())
