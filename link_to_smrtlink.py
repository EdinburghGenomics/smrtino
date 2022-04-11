#!/usr/bin/env python3

""" Small shell wrapper to discover links to SMRTLink
"""
import os, sys
from smrtino.ParseXML import get_readset_info

# We need to know the base URL for smrtlink. Rather than pulling in ARgumentParser, just make it an
# env var.
sb = os.environ.get('SMRTLINK_BASE')
if not sb:
    exit(f"You need to set $SMRTLINK_BASE - try 'env SMRTLINK_BASE=https://smrtlink/sl {sys.argv[0]} ...' or so")

if not sys.argv[1:]:
    exit(f"Usage: {sys.argv[0]} <xml_file> [...]")

for xmlfile in sys.argv[1:]:

    ri = get_readset_info(xmlfile, smrtlink_base=sb)

    print(ri['_link'])
