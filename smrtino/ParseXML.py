#!/usr/bin/env python3
import re
import logging as L
import xml.etree.ElementTree as ET

from . import squash_barcode

""" For each cell we have a metadata.xml file which has info on the whole cell
    (and the run).
    For each barcode we have a readset.xml file which has info on the sample,
    but also some info on the whole cell.

    If you run a function on the wrong type of file you'll get an error.
"""

_ns = dict( pbmeta   = 'http://pacificbiosciences.com/PacBioCollectionMetadata.xsd',
            pb       = 'http://pacificbiosciences.com/PacBioDatasets.xsd',
            pbmodel  = 'http://pacificbiosciences.com/PacBioDataModel.xsd',
            pbbase   = 'http://pacificbiosciences.com/PacBioBaseDataModel.xsd',
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

def _get_automation_parameters(root):
    """Return the AutomationParameter list as a regular dict

       We'll squish all the AutomationParameters into one dict, until
       I see a reason not to.
    """
    res = {}
    ap_list = [ *root.findall('.//pbbase:AutomationParameter', _ns),
                *root.findall('.//pbmeta:AutomationParameter', _ns) ]

    for ap in ap_list:
        k = ap.attrib['Name']
        dtype = ap.attrib['ValueDataType']
        val = ap.attrib['SimpleValue']

        if k in res:
            raise KeyError(f"AutomationParameter {k} is repeated in XML.")

        if dtype == "Boolean" or k in ["DynamicLoadingCognate"]:
            # At least some booleans are tagged as strings, hence the special case
            res[k] = val == "True"
        elif dtype == "String":
            res[k] = val
        elif dtype == "Double":
            res[k] = float(val)
        elif dtype == "Int32":
            res[k] = int(val)

    return res

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
        info['barcodes'] = [ squash_barcode(bc.attrib.get('Name', 'unknown'))
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
    if ec is not None:
        run_info['ExperimentId'] = ec.attrib.get('ExperimentId', '')

    # And there should be a Run element which provides us, eg.
    # ChipType="8mChip" InstrumentType="Sequel2e" CreatedBy="rfoster2"
    run = root.find('.//pbmodel:Run', _ns)
    if run is not None:
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

def get_metadata_info2(xmlfile):
    """ Read some stuff from the metadata/{cellid}.metadata.xml file that
        relates to the whole run.
        Except, different stuff to the function above.

            { cell_id
              cell_uuid
              run_id
              run_slot
              ws_name
              ws_desc

              run_start
              application
              adaptive_loading
              movie_time
              smrt_cell_lot_number
              insert_size
              on_plate_loading_conc }
    """
    run_info = dict()

    root = _load_xml(xmlfile)
    if root.tag != f"{{{_ns['pbmodel']}}}PacBioDataModel":
        raise RuntimeError("This function must be run on a metadata.xml file."
                           f" Root tag is: {root.tag}.")

    # The first of these can be got by _get_common_stuff so use that, but ensure
    # everything really is listed.
    common_stuff = _get_common_stuff(root)
    for k in "cell_id cell_uuid run_id run_slot ws_name ws_desc".split():
        run_info[k] = common_stuff[k]

    aps = _get_automation_parameters(root)
    cellpac = _get_cellpac(root)
    runattribs = _get_runelem(root)

    cmd = root.find('.//pbmeta:CollectionMetadata', _ns)
    run_info['instrument_id'] = cmd.attrib['InstrumentId']
    run_info['instrument_name'] = cmd.attrib['InstrumentName']

    # I could parse this properly, but instead just take the first chars
    mo = re.match(r"(\d{4}-\d{2}-\d{2})T", runattribs['WhenStarted'])
    run_info['run_start'] = mo.group(1)
    run_info['smrtlink_user'] = runattribs['CreatedBy']

    ws_application = root.find('.//pbmeta:WellSample/pbmeta:Application', _ns)
    run_info['application'] = ws_application.text

    # adaptive_loading
    run_info['adaptive_loading'] = aps.get('DynamicLoadingCognate')

    # movie_time
    run_info['movie_time'] = round(aps['MovieLength'] / 60)

    # smrt_cell_lot_number and smrt_cell_barcode
    run_info['smrt_cell_lot_number'] = cellpac['LotNumber']
    run_info['smrt_cell_label_number'] = cellpac['LabelNumber']
    if cellpac['Barcode'] != cellpac['LabelNumber']:
        L.warning(f"Cell Barcode({cellpac['Barcode']}) and LabelNumber({cellpac['LabelNumber']})"
                  f" are expected to be the same nowadays.")

    # insert_size - this could be in two places
    run_info['insert_size'] = int(root.find('.//pbmeta:InsertSize', _ns).text)
    if ('InsertSize' in aps) and (run_info['insert_size'] != aps['InsertSize']):
        raise ValueError("Insert size mismatch in XML")

    # on_plate_loading_conc
    run_info['on_plate_loading_conc'] = int(
                    root.find('.//pbmeta:OnPlateLoadingConcentration', _ns).text )

    # software versions
    vi = { e.attrib['Name']: e.attrib.get('Version', 'unknown') for e in
           root.findall('.//pbmeta:ComponentVersions/pbmeta:VersionInfo', _ns) }
    run_info['version_ics'] = vi['ics']
    run_info['version_chemistry'] = vi['chemistry']
    run_info['version_smrtlink'] = vi['smrtlink']

    return run_info

def _get_cellpac(root):
    """Get the CellPac element attribs
    """
    return root.find('.//pbmeta:CellPac', _ns).attrib

def _get_runelem(root):
    """Get the Run element
    """
    return root.find('.//pbmodel:Runs/pbmodel:Run', _ns).attrib

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

    # Get the barcode according to the filename
    # This regex may capture "bc0001.mas16" so we need to chop off any
    # extra extension
    mo = re.search(r"_reads\.(\S+)\.(consensus)?readset.xml$", xmlfile)
    barcode_from_filename = mo.group(1).split(".")[0] if mo else "unknown"

    # There should be, unless this !
    L.debug(f"Found {len(bio_samples)} BioSample records, {len(samp_barcodes)}+{len(meta_barcodes)} DNABarcodes")

    # The presence of meta_barcodes is indicative of an unassigned reads file.
    if meta_barcodes:
        assert 'barcodes' not in info
        info['bs_name'] = "unassigned"
        info['bs_desc'] = "Unassigned reads"

    elif len(bio_samples) == 1:
        # A single sample. We should already have the barcode (or there's no barcode), but check.
        if len(samp_barcodes) == 0:
            # Not a barcoded run
            assert 'barcodes' not in info
        else:
            # This assertion is an internal consistency check and should pass regardless
            # of the data content.
            assert info['barcodes'] == [squash_barcode(e.attrib['Name']) for e in samp_barcodes]
            # Verify that info['barcode'] really is the same as barcode_from_filename but this
            # could be squashed or unsquashed.
            barcode_from_xml, = info['barcodes']
            if squash_barcode(barcode_from_filename) != barcode_from_xml:
                raise RuntimeError(f"Barcode {barcode_from_xml!r} in file does not match"
                                   f" {barcode_from_filename!r} in the file name.")

            info['barcode'] = barcode_from_filename
            info['barcode_squashed'] = squash_barcode(info['barcode'])
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

