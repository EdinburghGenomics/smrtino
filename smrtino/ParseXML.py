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

_ns = dict( pbmeta   = 'http://pacificbiosciences.com/PacBioCollectionMetadata.xsd',
            pb       = 'http://pacificbiosciences.com/PacBioDatasets.xsd',
            pbmodel  = 'http://pacificbiosciences.com/PacBioDataModel.xsd',
            pbsample = 'http://pacificbiosciences.com/PacBioSampleInfo.xsd', )

rs_constants = dict( Revio = \
                        dict( label = 'Revio (HiFi)',
                              shortname = 'ccsreads',
                              parts = ['hifi_reads', 'fail_reads'] ),
                     ConsensusReadSet = \
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

def _bcmunge(bc):
    """If we see a barcode like "bc1002--bc1002" then just report "bc1002"
    """
    bc_split = bc.split("--")

    if len(bc_split) == 2 and bc_split[0] == bc_split[1]:
        return bc_split[0]
    else:
        return bc

def _get_common_stuff(root):
    """There is a lot of overlap between what make_summary.py wants from the metadata
       file and compile_bc_info.py wants from the readset file.

       This function captures that.
    """
    try:
        rf = root.find('.//pbmeta:ResultsFolder', _ns).text.rstrip('/')
        cmd = root.find('.//pbmeta:CollectionMetadata', _ns).attrib
        crs = root.find('.//pbmeta:ConsensusReadSetRef', _ns).attrib
    except AttributeError:
        rf = "/unknown/unknown"
        cmd = {}
        crs = {}

    info = { 'run_id':     rf.split('/')[-2],
             'run_slot':   rf.split('/')[-1], # Also could get this from TimeStampedName
             'cell_id':    cmd.get('Context', "unknown"),
             'cell_uuid' : crs.get('UniqueId', "no-uuid") }

    # See if this is a ConsensusReadSet (HiFi) or SubreadSet (CLR)
    #root_tag = re.sub(r'{.*}', '', root.tag)
    #constants = rs_constants.get(root_tag, {})
    # Actually I'm just going to hard-code this to the Revio settings. We can revisit if
    # they ever change.
    constants = rs_constants['Revio']

    info['readset_type'] = constants['label']
    info['_readset_type'] = constants['shortname']
    info['_parts'] = constants['parts']

    # All these files should have a single WellSample, until I see otherwise.
    # For the metadata for a pooled run there may be several biosamples.
    well_samples = root.findall('.//pbmeta:WellSample', _ns)

    # There should be 1!
    L.debug(f"Found {len(well_samples)} WellSample records")

    if len(well_samples) == 1:
        ws, = well_samples

        info['ws_name'] = ws.attrib.get('Name', '')
        info['ws_desc'] = ws.attrib.get('Description', '')

        mo = re.search(r'\b(\d{5,})', info['ws_name'])
        if mo:
            # There is also a bs_project bit it should (!) be the same.
            info['ws_project'] = mo.group(1)

    # And see if we have barcodes
    dna_barcodes = ws.findall(".//pbsample:DNABarcodes", _ns)
    if dna_barcodes:
        info['barcodes'] = [ _bcmunge(bc.attrib.get('Name', 'unknown'))
                             for dna in dna_barcodes
                             for bc in dna ]

    return info



def get_metadata_summary(xmlfile, smrtlink_base=None):
    """ Glean info from the metadata.xml file for a contents of the Revio SMRT cell.

        This is used to get the info before the pipeline actually runs - the report
        maker gets this same info from the readset.xml file.
    """
    root = _load_xml(xmlfile)

    if root.tag != f"{{{_ns['pbmodel']}}}PacBioDataModel":
        raise RuntimeError("This function must be run on a metadata.xml file."
                           f" Root tag is: {root.tag}.")

    info = _get_common_stuff(root)

    if smrtlink_base:
        info['_link'] = get_smrtlink_link(root, smrtlink_base)

    return info

def get_metadata_info(xmlfile):
    """ Read some stuff from the metadata/{cellid}.metadata.xml file that
        relates to the whole run.
    """
    run_info = dict(ExperimentId = 'unknown')

    root = _load_xml(xmlfile)

    if root.tag != f"{{{_ns['pbmodel']}}}PacBioDataModel":
        raise RuntimeError("This function must be run on a metadata.xml file."
                           f" Root tag is: {root.tag}.")

    # attribute if one was set.
    ec = root.find('pbmodel:ExperimentContainer', _ns)
    if ec:
        run_info['ExperimentId'] = ec.attrib.get('ExperimentId', '')

    # And there should be a Run element which provides us, eg.
    # ChipType="8mChip" InstrumentType="Sequel2e" CreatedBy="rfoster2"
    run = root.find('.//pbmodel:Run', _ns)
    if run:
        for i in "ChipType InstrumentType CreatedBy TimeStampedName".split():
            run_info[i] = run.attrib.get(i, 'unknown')

    # And there should be a CollectionMetadata element which gives us the InstrumentId
    # Except this is now under "Run", even though the name is under "CollectionMetadata"?
    rmd = root.find('.//pbmeta:Run', _ns)
    if rmd:
        for i in ["InstrumentId"]:
            run_info[i] = rmd.attrib.get(i, 'unknown')

        if "InstrumentType" in run_info:
            run_info["Instrument"] = f"{run_info['InstrumentType']}_{run_info['InstrumentId']}"

    # Get the WellSample name which is presumably the pool name
    return run_info

def get_readset_info(xmlfile, smrtlink_base=None):
    """ Glean info from a readset file for a SMRT cell
    """
    root = _load_xml(xmlfile)

    if root.tag != f"{{{_ns['pb']}}}ConsensusReadSet":
        raise RuntimeError("This function must be run on a readset.xml file."
                           f" Root tag is: {root.tag}.")

    info = _get_common_stuff(root)

    # For a readset there should be one biosample with one barcode.
    # It might or might not have the same name as the wellsample (depending on if the wellsample was a pool).
    # Unassigned readsets will, confusingly, have one or more BioSamples but the barcodes will be
    # 'pbmeta:DNABarcode' tags not 'pbsample:DNABarcode' tags.
    bio_samples = root.findall('.//pbmeta:WellSample/pbsample:BioSamples/pbsample:BioSample', _ns)
    samp_barcodes = [ mbc for bs in bio_samples
                      for mbc in bs.findall('pbsample:DNABarcodes/pbsample:DNABarcode', _ns) ]
    meta_barcodes = [ mbc for bs in bio_samples
                      for mbc in bs.findall('pbmeta:DNABarcodes/pbmeta:DNABarcode', _ns) ]

    # There should be, unless this !
    L.debug(f"Found {len(bio_samples)} BioSample records, {len(samp_barcodes)}+{len(meta_barcodes)} DNABarcodes")

    if meta_barcodes:
        # This is indicative of an unassigned reads file, as far as I can see.
        assert 'barcodes' not in info
        info['bs_name'] = "unassigned"
        info['bs_desc'] = "Unassigned reads"

    elif len(bio_samples) == 1:
        # A single sample. We should already have the barcode (or there's no barcode), but check.
        if len(samp_barcodes) == 0:
            assert 'barcodes' not in info
        else:
            assert info['barcodes'] == [_bcmunge(e.attrib['Name']) for e in samp_barcodes]
            info['barcode'], = info['barcodes']
            del info['barcodes']

        bs, = bio_samples

        info['bs_name'] = bs.attrib.get('Name', '')
        info['bs_desc'] = bs.attrib.get('Description', '')

        mo = re.search(r'\b(\d{5,})', info['bs_name'])
        if mo:
            info['bs_project'] = mo.group(1)

    else:
        # Maybe should be an actual error?
        L.warning(f"We should not have {len(bio_samples)} BioSample entries in one readset XML file.")

    # We should have a single project which is both 'bs_project' and 'ws_project',
    # but if they disagree then believe the sample name over the pool name.
    if 'bs_project' in info:
        if info['bs_project'] != info['ws_project']:
            L.warning("Project name mismatch")
        # Take the project from the sample in any case
        info['project'] = info['bs_project']
    else:
        # Really? Could be a test run and not have a project.
        info['project'] = info.get('ws_project') or "none"

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

