#!/usr/bin/env python3
import re
import logging as L
import xml.etree.ElementTree as ET

""" Parses the subreadset.xml files based upon out interpretation.
    To use:
        from smrtino.ParseXML import get_subreadset_info
        info = get_subreadset_info(filename)
"""

_ns = dict( pbmeta = 'http://pacificbiosciences.com/PacBioCollectionMetadata.xsd',
            pb     = 'http://pacificbiosciences.com/PacBioDatasets.xsd' )

def get_subreadset_info(xmlfile):
    """ Glean info from the file as per scan_for_smrt_cells in get_pacbio_yml.py
    """
    root = ET.parse(xmlfile).getroot()

    try:
        rf = root.find('.//pbmeta:ResultsFolder', _ns).text.rstrip('/')
        cmd = root.find('.//pbmeta:CollectionMetadata', _ns).attrib
    except AttributeError:
        rf = "/unknown/unknown"
        cmd = {'Context': 'unknown'}

    info = { 'run_id': rf.split('/')[-2],
             'run_slot': rf.split('/')[-1], # Also could get this from TimeStampedName
             'cell_id': cmd.get('Context') }

    well_samples = root.findall('.//pbmeta:WellSample', _ns)
    # There should be 1!
    L.debug("Found {} WellSample records".format(len(well_samples)))

    if len(well_samples) == 1:
        ws, = well_samples

        info['ws_name'] = ws.attrib.get('Name', '')
        info['ws_desc'] = ws.attrib.get('Description', '')

        mo = re.match('\d+', info['ws_name'])
        if mo:
            info['ws_project'] = mo.group(0)

    return info
