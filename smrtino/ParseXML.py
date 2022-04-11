#!/usr/bin/env python3
import re
import logging as L
import xml.etree.ElementTree as ET

""" Parses the subreadset.xml files based upon our interpretation.
    To use:
        from smrtino.ParseXML import get_readset_info
        info = get_readset_info(filename)
"""

_ns = dict( pbmeta = 'http://pacificbiosciences.com/PacBioCollectionMetadata.xsd',
            pb     = 'http://pacificbiosciences.com/PacBioDatasets.xsd' )

rs_labels = dict( ConsensusReadSet = 'ConsensusReadSet (HiFi)',
                  SubreadSet       = 'SubreadSet (CLR)' )
rs_parts  = dict( ConsensusReadSet = ['reads'],
                  SubreadSet       = ['subreads', 'scraps'] )

def get_readset_info(xmlfile, smrtlink_base=None):
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

    # See if this is a ConsensusReadSet (HiFi) or SubreadSet (CLR)
    root_tag = re.sub(r'{.*}', '', root.tag)
    info['readset_type'] = rs_labels.get(root_tag, root_tag)
    info['_parts'] = rs_parts.get(root_tag, [])

    well_samples = root.findall('.//pbmeta:WellSample', _ns)
    # There should be 1!
    L.debug("Found {} WellSample records".format(len(well_samples)))

    if len(well_samples) == 1:
        ws, = well_samples

        info['ws_name'] = ws.attrib.get('Name', '')
        info['ws_desc'] = ws.attrib.get('Description', '')

        mo = re.search(r'\b(\d{5,})', info['ws_name'])
        if mo:
            info['ws_project'] = mo.group(1)

    if smrtlink_base:
        info['_link'] = get_smrtlink_link(root, smrtlink_base)

    return info

def get_smrtlink_link(root, base_url):
    """Construct a link to SMRTLink, like:

       https://smrtlink.genepool.private:8243/sl/data-management/dataset-detail/fc816e69-8ebd-4905-9bd1-4678607869f2?type=subreads

       In which case, base_url would be https://smrtlink.genepool.private:8243/sl
    """
    # The dstype parameter needs to be 'ccsreads' or 'subreads'
    rs_types  = dict( ConsensusReadSet = 'ccsreads',
                      SubreadSet       = 'subreads' )

    root_tag = re.sub(r'{.*}', '', root.tag)
    rstype = rs_types.get(root_tag, 'unknown')

    # The UniqueId is just an attrib of the root element (though it is also found elsewhere)
    uniqueid = root.attrib.get('UniqueId', 'no_UniqueId_in_xml')

    return f"{base_url}/data-management/dataset-detail/{uniqueid}?type={rstype}"

