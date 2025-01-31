#!/usr/bin/env python3
import sys, re
from io import StringIO

from lxml import etree

def main():
    parser = etree.XMLParser(remove_blank_text=True)
    file_obj = StringIO()

    # Remove any XML declaration and assume the file is utf-8
    # This breaks the XML standard, but PacBio broke it first!
    first_line = next(sys.stdin)
    first_line = re.sub(r"<\?xml [^?>]+\?>", "", first_line)
    if first_line.strip():
        file_obj.write(first_line)
    for l in sys.stdin:
        file_obj.write(l)
    file_obj.seek(0)

    tree = etree.parse(file_obj, parser)
    sys.stdout.buffer.write(etree.tostring(tree, pretty_print=True))

if __name__ == '__main__':
    main()
