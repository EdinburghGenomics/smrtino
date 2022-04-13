#!/usr/bin/env python3

"""Test for the SMRTLink API wrapper
   We'll avoid tests that require an actual connection.
"""

# Note this will get discovered and run as a test. This is fine.

import sys, os, re
import unittest
import logging

VERBOSE = os.environ.get('VERBOSE', '0') != '0'

from smrtino.SMRTLink import SMRTLinkClient

class T(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        #Prevent the logger from printing messages - I like my tests to look pretty.
        if VERBOSE:
            logging.getLogger().setLevel(logging.DEBUG)
        else:
            logging.getLogger().setLevel(logging.CRITICAL)

    def setUp(self):
        # See the errors in all their glory
        self.maxDiff = None

    ### THE TESTS ###
    def test_pre_connect(self):

        client = SMRTLinkClient("dummy.host")

        self.assertEqual( client.get_api_base(),
                          "https://dummy.host:8243/SMRTLink/1.0.0" )

        self.assertEqual( client.get_api_base("https://foo:1234"),
                          "https://foo:1234/SMRTLink/1.0.0" )

if __name__ == '__main__':
    unittest.main()
