#!/usr/bin/env python3

"""Yet another script to calculate some stats over a FASTA file
"""
import os, sys
from collections import namedtuple, OrderedDict
from itertools import islice
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter

from smrtino.YAMLOrdered import yaml

fastaline = namedtuple('fastaline', 'length atgc_bases gc_bases'.split())

def read_fasta(fh, trim_n=False):
    """Reads lines from a FASTA file, and for each returns the total length and the
       GC content. You can opt to trim N's from the end.
    """
    # Length and GC for the current read. We also need atgc count so N's don't skew
    # the GC calculation.
    length = atgc = gc = 0
    # Count of reads read
    count = 0

    for l in fh:
        if l.startswith('>'):
            if count:
                yield(fastaline(length, atgc, gc))
            count += 1
            length = atgc = gc = 0
        else:
            l = l.strip()
            if trim_n:
                l = l.strip('Nn')
            atgc += sum( 1 for n in l if n in 'ATGCatgc' )
            gc   += sum( 1 for n in l if n in 'GCgc' )
            length += len(l)
    if count:
        yield(fastaline(length, atgc, gc))

def fasta_to_histo(fastalines):
    """Reads fastaline tuples as produced by read_fasta(...) and retuns a histogram (a list) of
       dict(tally=..., atgc_bases=..., gc_bases=...)
    """
    res = list()

    for fline in fastalines:
        if fline.length > len(res) - 1:
            res.extend( dict(tally=0, atgc_bases=0, gc_bases=0) for _ in range(len(res) - 1, fline.length) )
        res[fline.length]['tally'] += 1
        res[fline.length]['atgc_bases'] += fline.atgc_bases
        res[fline.length]['gc_bases'] += fline.gc_bases

    return res

def histo_to_result(histo, cutoff):
    """ Do some calculations on the histogram.
    """
    res = OrderedDict([ ('Max read length', len(histo) - 1) ])

    if cutoff:
        def labelize(l):
            if 'reads' in l.lower():
                return "{} >={}".format(l, cutoff)
            else:
                return "{} for reads >={}".format(l, cutoff)
    else:
        labelize = str

    # Total reads and bases
    total_reads = sum( h['tally'] for h in histo[cutoff:] )
    total_length = sum( n * h['tally'] for n, h in islice(enumerate(histo), cutoff, None) )

    res[labelize('Reads')] = total_reads
    res[labelize('Total bases')] = total_reads

    # N50 - see notes
    # If the cutoff is larger than the longert sequence the N50 will be the length
    # or the longest sequence(!?)
    half_length = (total_length // 2) + (total_length % 2)
    sum_length = 0
    for i in reversed(range(len(histo))):
        sum_length += (i * histo[i]['tally'])
        if sum_length >= half_length:
            res[labelize('N50')] = i
            break
    else:
        res[labelize('N50')] = -1


    res['_histo'] = histo

    return res

def main(args):

    if not args.fastafile or args.fastafile == '-':
        histo = fasta_to_histo(read_fasta(sys.stdin, trim_n = args.trim_n))
    else:
        with open(args.fastafile) as fh:
            histo = fasta_to_histo(read_fasta(fh, trim_n = args.trim_n))

    print( yaml.safe_dump(histo_to_result(histo, args.cutoff or 0)) )


def parse_args(*args):
    description = """Reads a FASTA file and outputs some stats. Yes, it's yet another
                     FASTA stats script.
                  """
    argparser = ArgumentParser( description=description,
                                formatter_class = ArgumentDefaultsHelpFormatter )
    argparser.add_argument("fastafile", nargs='?',
                            help="File to read, or else will read from stdin.")
    argparser.add_argument("-c", "--cutoff",
                            help="Min length cutoff for the stats.")
    argparser.add_argument("-t", "--trim_n", action="store_true",
                            help="Trim off N's from the start and end of reads.")

    return argparser.parse_args(*args)

if __name__ == "__main__":
    main(parse_args())
