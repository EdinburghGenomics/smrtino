#!/usr/bin/env python3

# Strip some links to files from the consensusreadset.xml what we are processing.

# 1) load the XML
# 2) Prune out the pbds:ConsensusReadSet/pbbase:ExternalResources/pbbase:ExternalResource/pbbase:ExternalResources node
# 3) Rename unbarcoded files to add .all to the filenames
# 4) Print the result

import sys, re
import xml.etree.ElementTree as ET

# What to get rid of...
nsmap = dict( pbbase   = "http://pacificbiosciences.com/PacBioBaseDataModel.xsd",
              pbdm     = "http://pacificbiosciences.com/PacBioDataModel.xsd",
              pbmeta   = "http://pacificbiosciences.com/PacBioCollectionMetadata.xsd",
              pbpn     = "http://pacificbiosciences.com/PacBioPartNumbers.xsd",
              pbrk     = "http://pacificbiosciences.com/PacBioReagentKit.xsd",
              pbsample = "http://pacificbiosciences.com/PacBioSampleInfo.xsd",
              pbds     = "http://pacificbiosciences.com/PacBioDatasets.xsd" )

prune = [ "pbds:SubreadSet/pbbase:ExternalResources/pbbase:ExternalResource/pbbase:ExternalResources",
          "pbds:ConsensusReadSet/pbbase:ExternalResources/pbbase:ExternalResource/pbbase:ExternalResources",
          "pbds:ConsensusReadSet/pbbase:SupplementalResources"]

def main(fh):
    tree = ET.parse(fh)

    for p in prune:
        remove_path(tree, None, p.split('/'))

    chop_resourceids(tree.getroot())

    if unbarcoded_file_rename(tree.getroot()):
        # Now we replace all the pbsample:DNABarcode[s] with pbmeta:DNABarcode[s]
        meta_ise_barcodes(tree.getroot())

    print('<?xml version="1.0" encoding="utf-8"?>')
    tree.write(sys.stdout, "unicode")
    print()

def meta_ise_barcodes(elem):
    """Is this the unassigned file? Then it should look like the unassigned file!!
    """
    for bcs_elem in elem.iterfind('.//pbsample:DNABarcodes', nsmap):
        bcs_elem.tag = f"{{{nsmap['pbmeta']}}}DNABarcodes"
        for bc_elem in bcs_elem.iterfind('pbsample:DNABarcode', nsmap):
            bc_elem.tag = f"{{{nsmap['pbmeta']}}}DNABarcode"

def unbarcoded_file_rename(elem):
    """This is getting even hackier. Walk the whole XML tree and insert .all into the
       filenames of reads without a barcode name because the pipeline is renaming these files so
       we need to munge the XML too.

       Also, when processing re-demultiplexed reads, the 'unbarcoded' reads are being
       renamed to 'unassigned', so we need to correct this too.

       And don't get me started on the re-demultiplex XML using the wrong tags for the
       barcodes.
    """
    unbarcoded_flag = False

    # I could do this on the same pass as chop_resourceids() but I want to keep
    # my hacks separate.
    if 'ResourceId' in elem.attrib:
        elem.attrib['ResourceId'] = re.sub( r"_reads\.bam(?=\.pbi$|$)",
                                            "_reads.all.bam",
                                            elem.attrib['ResourceId'] )
        elem.attrib['ResourceId'] = re.sub( r"_reads\.unbarcoded\.bam(?=\.pbi$|$)",
                                            "_reads.unassigned.bam",
                                            elem.attrib['ResourceId'] )

        if re.search( r"_reads\.unassigned\.bam$",
                      elem.attrib['ResourceId'] ):
            unbarcoded_flag = True

    # Drill down
    for child in elem:
        unbarcoded_flag = unbarcoded_file_rename(child) or unbarcoded_flag

    return unbarcoded_flag

def chop_resourceids(elem):
    r"""Walk the whole XML tree and if we see a ResourceId attribute that
        starts with "../\w+_reads/" then chop that off.
     """
    if 'ResourceId' in elem.attrib:
        elem.attrib['ResourceId'] = re.sub( r"^\.\./\w+_reads/",
                                            "",
                                            elem.attrib['ResourceId'] )

    # Drill down
    for child in elem:
        chop_resourceids(child)

def remove_path(pnode, ppnode, path):
    """Remove all nodes matching the path. For consistency, apply at all levels.
       We need to track the parent node as ElementTree does not.
    """

    # Special handling if pnode is actually a document.
    try:
        root = pnode.getroot()
        ns, tn = path[0].split(':')
        if root.tag != "{{{}}}{}".format(nsmap[ns],tn):
            # Shtop. Root node name mismatch.
            return
        remove_path(root, pnode, path[1:])
    except AttributeError:
        # Keep going we're not dealing with a root node.
        pass

    if not path:
        # We reached a leaf. Remove it.
        ppnode.remove(pnode)
    else:
        for cnode in pnode.findall(path[0], nsmap):
            remove_path(cnode, pnode, path[1:])

main(sys.argv[1])
