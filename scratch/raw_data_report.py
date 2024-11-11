# See if I can read .zmw_metrics.csv.gz

import os, sys, re
from pprint import pprint

headers = next(sys.stdin).strip().split(",")
assert headers == ['read_length', 'pol_length', 'read_qual', 'hifi', 'num_passes', 'zmw_id']

# read_qual is a float, everything else in an int
type_foo = dict( read_qual = float )
type_list = [ type_foo.get(h, int) for h in headers ]

total_length = 0

for l in sys.stdin:
    l = l.strip().split(",")

    l_dict = dict(zip(headers, [t(l) for t, l in  zip(type_list, l)]))

    if l_dict['read_length'] > 0:
        total_length += l_dict['read_length']

print(total_length)
