#!/usr/bin/env python3

# Strip some links to files from the consensusreadset.xml what we are processing.

# 1) load the XML
# 2) Prune out the pbds:ConsensusReadSet/pbbase:ExternalResources/pbbase:ExternalResource/pbbase:ExternalResources node
# 3) Print the result

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
          "pbds:ConsensusReadSet/pbbase:ExternalResources/pbbase:ExternalResource/pbbase:ExternalResources" ]

def main(fh):
    tree = ET.parse(fh)

    for p in prune:
        remove_path(tree, None, p.split('/'))

    chop_resourceids(tree.getroot())

    print('<?xml version="1.0" encoding="utf-8"?>')
    tree.write(sys.stdout, "unicode")
    print()

def chop_resourceids(elem):
    """Walk the whole XML tree and if we see a ResourceId attribute that
       starts with "../\w+_reads/" then chop that off.
    """
    if 'ResourceId' in elem.attrib:
        elem.attrib['ResourceId'] = re.sub(r"^\.\./\w+_reads/", "", elem.attrib['ResourceId'])

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
