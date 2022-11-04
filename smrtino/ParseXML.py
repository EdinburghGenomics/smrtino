#!/usr/bin/env python3
import re
import logging as L
import xml.etree.ElementTree as ET

""" Parses the subreadset.xml files based upon our interpretation.
    To use:
        from smrtino.ParseXML import get_readset_info
        info = get_readset_info(filename)
"""

_ns = dict( pbmeta  = 'http://pacificbiosciences.com/PacBioCollectionMetadata.xsd',
            pb      = 'http://pacificbiosciences.com/PacBioDatasets.xsd',
            pbmodel = 'http://pacificbiosciences.com/PacBioDataModel.xsd' )

rs_constants = dict( ConsensusReadSet = \
                        dict( label = 'ConsensusReadSet (HiFi)',
                              shortname = 'ccsreads',
                              parts = ['reads'] ),
                     SubreadSet       = \
                        dict( label = 'SubreadSet (CLR)',
                              shortname = 'subreads',
                              parts = ['subreads', 'scraps'] ) )

def get_runmetadata_info(xmlfile):
    """ Read some stuff from the run.metadata.xml file
    """
    res = dict(ExperimentId = 'unknown')

    root = ET.parse(xmlfile).getroot()

    # attribute if one was set.
    ec = root.find('pbmodel:ExperimentContainer', _ns)
    if ec:
        res['ExperimentId'] = ec.attrib.get('ExperimentId', 'none set')

    # And there should be a Run element which provides us, eg.
    # ChipType="8mChip" InstrumentType="Sequel2e" CreatedBy="rfoster2"
    run = root.find('.//pbmodel:Run', _ns)
    if run:
        for i in "ChipType InstrumentType CreatedBy TimeStampedName".split():
            res[i] = run.attrib.get(i, 'unknown')

    # And there should be a CollectionMetadata element which gives us the InstrumentId
    cmd = root.find('.//pbmeta:CollectionMetadata', _ns)
    if cmd:
        for i in ["InstrumentId"]:
            res[i] = cmd.attrib.get(i, 'unknown')

        if "InstrumentType" in res:
            res["Instrument"] = f"{res['InstrumentType']}_{res['InstrumentId']}"

    return res

def get_readset_info(xmlfile, smrtlink_base=None):
    """ Glean info from a readset file for a SMRT cell
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
             'cell_id': cmd.get('Context'),
             'cell_uuid' : root.attrib.get('UniqueId', 'no-uuid') }

    # See if this is a ConsensusReadSet (HiFi) or SubreadSet (CLR)
    root_tag = re.sub(r'{.*}', '', root.tag)
    constants = rs_constants.get(root_tag, {})

    # FIXME - I should probably fail if the root_tag is unrecongised, rather than emitting
    # plausible junk.
    info['readset_type'] = constants.get('label', root_tag)
    info['_readset_type'] = constants.get('shortname', root_tag.lower())
    info['_parts'] = constants.get('parts', [])

    well_samples = root.findall('.//pbmeta:WellSample', _ns)
    # There should be 1!
    L.debug(f"Found {len(well_samples)} WellSample records")

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

       In which case, base_url would be https://smrtlink.genepool.private:8243

       This does work, but I'm actually going to construct these links in the link_to_smrtlink.py script which will
       read in the info.yml, rather than going back to the XML.
    """
    root_tag = re.sub(r'{.*}', '', root.tag)
    rstype = rs_constants[root_tag]['shortname']

    # The UniqueId is just an attrib of the root element (though it is also found elsewhere)
    uniqueid = root.attrib.get('UniqueId', 'no_UniqueId_in_xml')

    return f"{base_url}/sl/data-management/dataset-detail/{uniqueid}?type={rstype}"

