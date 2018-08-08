#!/usr/bin/env python3
import os, sys, re
import logging as L
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter

""" Starting point for a Python script
"""
def main(args):

    L.basicConfig(level=(L.DEBUG if args.debug else L.WARNING))


def parse_args(*args):
    description = """ TODO
                  """
    argparser = ArgumentParser( description=description,
                                formatter_class = ArgumentDefaultsHelpFormatter )
    argparser.add_argument("-f", "--foo", required=True, type=string, nargs=1,
                            help=" TODO ")
    argparser.add_argument("-d", "--debug", action="set_true",
                            help="Print more verbose debugging messages.")

    return argparser.parse_args(*args)


if __name__ == "__main__":
    main(parse_args())
