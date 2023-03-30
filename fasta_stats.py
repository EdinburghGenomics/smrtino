#!/usr/bin/env python3

"""Yet another script to calculate some stats over a FASTA file
"""
import os, sys
from collections import namedtuple, OrderedDict
from itertools import islice
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter

from smrtino import dump_yaml

fastaline = namedtuple('fastaline', 'length at_bases gc_bases'.split())

def read_fasta(fh, trim_n=False):
    """Reads lines from a FASTA file, and for each returns the total length and the
       GC content. You can opt to trim N's from the end.
    """
    # Length and GC for the current read. We also need both at and gc count so N's
    # don't skew the GC calculation.
    length = at = gc = 0
    # Count of reads read
    count = 0

    for l in fh:
        if l.startswith('>'):
            if count:
                yield(fastaline(length, at, gc))
            count += 1
            length = at = gc = 0
        else:
            l = l.strip()
            if trim_n:
                l = l.strip('Nn')

            # This was my original atgc counter. It works but is slow.
            #atgc += sum( 1 for n in l if n in 'ATGCatgc' )
            # These variations are faster
            #atgc += sum( l.count(n) for n in 'ATGCatgc' )
            #atgc += len(re.findall('[ATGCatgc]', l))

            # But this is the best I found.
            at += sum( l.count(n) for n in 'ATat' )
            gc += sum( l.count(n) for n in 'GCgc' )

            length += len(l)
    if count:
        yield(fastaline(length, at, gc))

def fasta_to_histo(fastalines):
    """Reads fastaline tuples as produced by read_fasta(...) and retuns a histogram (a list) of
       dict(tally=..., at_bases=..., gc_bases=...)
    """
    res = list()

    for fline in fastalines:
        if fline.length > len(res) - 1:
            res.extend( dict(tally=0, at_bases=0, gc_bases=0) for _ in range(len(res) - 1, fline.length) )
        res[fline.length]['tally'] += 1
        res[fline.length]['at_bases'] += fline.at_bases
        res[fline.length]['gc_bases'] += fline.gc_bases

    return res

def histo_to_result(histo, cutoffs=(0,), headings=True):
    """ Do some calculations on the histogram.
    """
    res = OrderedDict()

    def labelize(l, cutoff):
        """Make a readable label and add it to the list of _headings
        """
        if not cutoff:
            newl = str(l)
        elif 'reads' in l.lower():
            newl = "{} >={}".format(l, cutoff)
        else:
            newl = "{} for reads >={}".format(l, cutoff)

        if headings:
            res.setdefault('_headings', []).append(newl)
        return newl

    res[labelize('Max read length', None)] = len(histo) - 1

    for cutoff in cutoffs:
        # Total reads and bases
        total_reads = sum( h['tally'] for h in histo[cutoff:] )
        total_length = sum( n * h['tally'] for n, h in islice(enumerate(histo), cutoff, None) )

        res[labelize('Reads', cutoff)] = total_reads
        res[labelize('Total bases', cutoff)] = total_length

        # N50 - see notes
        # If the cutoff is larger than the longest sequence the N50 will be the length
        # or the longest sequence(!?)
        half_length = (total_length // 2) + (total_length % 2)
        sum_length = 0
        for i in reversed(range(len(histo))):
            sum_length += (i * histo[i]['tally'])
            if sum_length >= half_length:
                res[labelize('N50', cutoff)] = i
                break
        else:
            res[labelize('N50', cutoff)] = -1

        # GC
        total_gc = sum( h['gc_bases'] for h in histo[cutoff:] )
        total_at = sum( h['at_bases'] for h in histo[cutoff:] )

        try:
            res[labelize('GC %', cutoff)] = total_gc / (total_at + total_gc) * 100
        except Exception:
            res[labelize('GC %', cutoff)] = 0.0

        # Mean length
        try:
            res[labelize('Mean length', cutoff)] = total_length / total_reads
        except Exception:
            res[labelize('Mean length', cutoff)] = 0.0

    return res

def main(args):

    if not args.fastafile or args.fastafile == '-':
        histo = fasta_to_histo(read_fasta(sys.stdin, trim_n = args.trim_n))
    else:
        with open(args.fastafile) as fh:
            histo = fasta_to_histo(read_fasta(fh, trim_n = args.trim_n))

    # Print the result to STDOUT
    print(dump_yaml(histo_to_result( histo,
                                     args.cutoff,
                                     headings=not(args.no_headings) )))

    # Save the histogram
    if args.histogram:
        with open(args.histogram, 'w') as hfh:
            for n, v in enumerate(histo):
                print('{}\t{}'.format(n, v['tally']), file=hfh)

def parse_args(*args):
    description = """Reads a FASTA file and outputs some stats. Yes, it's yet another
                     FASTA stats script.
                  """
    argparser = ArgumentParser( description=description,
                                formatter_class = ArgumentDefaultsHelpFormatter )
    argparser.add_argument("fastafile", nargs='?',
                            help="File to read, or else will read from stdin.")
    argparser.add_argument("-c", "--cutoff", type=int, nargs='+', default=(0,),
                            help="Min length cutoff (or multiple cutoffs) for the stats.")
    argparser.add_argument("-H", "--histogram",
                            help="Save histogram to the specified file.")
    argparser.add_argument("-n", "--no_headings", action="store_true",
                            help="Suppress listing out the _headings.")
    argparser.add_argument("-t", "--trim_n", action="store_true",
                            help="Trim off N's from the start and end of reads.")

    return argparser.parse_args(*args)

if __name__ == "__main__":
    main(parse_args())
