#!/usr/bin/env python3
import re
import logging as L
import xml.etree.ElementTree as ET

""" For each cell we have a metadata.xml file which has info on the whole cell
    (and the run).
    For each barcode we have a readset.xml file which has info on the sample,
    but also some info on the whole cell.

    If you run a function on the wrong type of file you'll get an error.
"""

_ns = dict( pbmeta  = 'http://pacificbiosciences.com/PacBioCollectionMetadata.xsd',
            pb      = 'http://pacificbiosciences.com/PacBioDatasets.xsd',
            pbmodel = 'http://pacificbiosciences.com/PacBioDataModel.xsd',
            pbsi    = 'http://pacificbiosciences.com/PacBioSampleInfo.xsd', )

rs_constants = dict( ConsensusReadSet = \
                        dict( label = 'ConsensusReadSet (HiFi)',
                              shortname = 'ccsreads',
                              parts = ['reads'] ),
                     SubreadSet       = \
                        dict( label = 'SubreadSet (CLR)',
                              shortname = 'subreads',
                              parts = ['subreads', 'scraps'] ) )

def _load_xml(filename):
    """XML file loader that deals with the SMRTLink 12 bug -
       the files claim to be utf-16. But they are not. FFS.

       The files saved to the output directory are fixed (and SMRTLink 13 fixes the
       bug anyway) but I leave this here for backwards compatibility.
    """
    with open(filename) as fh:
        munged_lines = ( re.sub(r"utf-16", r"utf-8", aline) if n == 0
                         else aline
                         for n, aline in enumerate(fh) )

        root = ET.fromstringlist(munged_lines)

    return root

def _get_common_stuff(root):
    """There is a lot of overlap between what make_summary.py wants from the metadata
       file and compile_bc_info.py wants from the readset file.

       This function captures that.
    """

def get_metadata_summary(xmlfile, smrtlink_base=None):
    """ Glean info from the metadata.xml file for a whole Revio SMRT cell

        This is used to get the info before the pipeline actually runs.
    """
    root = _load_xml(xmlfile)

    try:
        rf = root.find('.//pbmeta:ResultsFolder', _ns).text.rstrip('/')
        cmd = root.find('.//pbmeta:CollectionMetadata', _ns).attrib
    except AttributeError:
        rf = "/unknown/unknown"
        cmd = {'Context': 'unknown'}

    info = { 'run_id': rf.split('/')[-2],
             'run_slot': rf.split('/')[-1], # Also could get this from TimeStampedName
             'cell_id': cmd.get('Context'),
             'cell_uuid' : cmd.get('UniqueId', 'no-uuid') }

    # For Revio we're always a "Revio (HiFi)" readset, until we're not.
    info['readset_type'] = "Revio (HiFi)"
    info['_readset_type'] = "ccsreads"

    # FIXME - should really get this from sc_data, not hard-coded
    info['parts'] = ["hifi_reads", "fail_reads"]

    # See what's actually loaded on the cell (this is the same as for Sequel)
    well_samples = root.findall(".//pbmeta:WellSample", _ns)
    # There should be 1!
    L.debug(f"Found {len(well_samples)} WellSample records")

    if len(well_samples) == 1:
        ws, = well_samples

        info['ws_name'] = ws.attrib.get('Name', '')
        info['ws_desc'] = ws.attrib.get('Description', '')

        mo = re.search(r'\b(\d{5,})', info['ws_name'])
        if mo:
            info['ws_project'] = mo.group(1)

        # And see if we have barcodes
        dna_barcodes = ws.findall(".//pbsi:DNABarcodes", _ns)

        if dna_barcodes:
            info['barcodes'] = [ bc.attrib.get('Name', 'unknown')
                                 for dna in dna_barcodes
                                 for bc in dna ]

    if smrtlink_base:
        info['_link'] = get_smrtlink_link(root, smrtlink_base)

    return info

def get_metadata_info(xmlfile):
    """ Read some stuff from the metadata/{cellid}.metadata.xml file
    """
    run_info = dict(ExperimentId = 'unknown')

    root = _load_xml(xmlfile)

    # attribute if one was set.
    ec = root.find('pbmodel:ExperimentContainer', _ns)
    if ec:
        run_info['ExperimentId'] = ec.attrib.get('ExperimentId', 'none set')

    # And there should be a Run element which provides us, eg.
    # ChipType="8mChip" InstrumentType="Sequel2e" CreatedBy="rfoster2"
    run = root.find('.//pbmodel:Run', _ns)
    if run:
        for i in "ChipType InstrumentType CreatedBy TimeStampedName".split():
            run_info[i] = run.attrib.get(i, 'unknown')

    # And there should be a CollectionMetadata element which gives us the InstrumentId
    cmd = root.find('.//pbmeta:CollectionMetadata', _ns)
    if cmd:
        for i in ["InstrumentId"]:
            run_info[i] = cmd.attrib.get(i, 'unknown')

        if "InstrumentType" in run_info:
            run_info["Instrument"] = f"{run_info['InstrumentType']}_{run_info['InstrumentId']}"

    # Get the WellSample name which is presumably the pool name

    return dict( run = run_info,
                 ws_name = ws_name )

def get_readset_info(xmlfile, smrtlink_base=None):
    """ Glean info from a readset file for a SMRT cell
    """
    root = _load_xml(xmlfile)

    # FIXME - a lot of this is copy-paste from get_metadata_summary,
    # so break it out to a single function.

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

