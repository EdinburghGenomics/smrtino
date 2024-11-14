#!/usr/bin/env python3

"""Runs in the output directory, and prints a list of projects
   that are ready now.
   Will check for .done flags per-cell in pbpipeline,
   of for the global pbpipeline/aborted flag, therefore must be run after
   the flags are set in driver.py.
   Then reads sc_data.yaml and all the .info.yml files for the cells.
"""
import os, sys, re
from smrtino import glob, load_yaml
import logging as L

def find_projects_from_yaml(filename):
    """Get a list of all the projects from all the barcodes, given an
       info.yaml filemame.
    """
    ydata = load_yaml(filename)

    if 'barcodes' in ydata:
        # Resolve the @ lines
        for idx in range(len(ydata['barcodes'])):
            v = ydata['barcodes'][idx]
            if type(v) == str and v.startswith("@"):
                ydata['barcodes'][idx] = load_yaml(v[1:], relative_to=filename)

        # What should I do here if some barcodes have a project and others do not?
        # I'll make it an error for now.
        return (bc['ws_project'] for bc in ydata['barcodes'])
    else:
        return (ydata['ws_project'],)

def glob_sc_data():
    """If there is sc_data.yaml, use that. Else look for sc_data.*.yaml
    """
    g = glob("sc_data.yaml")
    if g:
        return g
    g = glob("sc_data.*.yaml")
    if g:
        return g

    raise FileNotFoundError("No match for 'sc_data.yaml' or 'sc_data.*.yaml'")

def list_the_projects():
    plist = []

    # Strategy is:

    # 1) Look in pbpipeline to see what cells are done
    if glob('pbpipeline/aborted'):
        return []

    # A cell should not really be both aborted and done, but .aborted takes precedence
    cells_done = [ c for f in
                   glob(r"pbpipeline/[0-9]_???.done") for c in
                   re.findall(r"(?<=/).+(?=\.)", f)
                   if not os.path.exists(f"pbpipeline/{c}.aborted") ]

    # 2) Load up sc_data.yaml. As of SMRTino 3.7 there may be multiple files
    # I could just glob() the info.yaml files directly but I want assurance that
    # everything is there as it should be.
    yaml_info_files = set()
    for sc_data_file in glob_sc_data():
        sc_data = load_yaml(sc_data_file)

        for acell, cdict in sc_data['cells'].items():
            if cdict['slot'] in cells_done:
                # It's a candidate
                yaml_info_files.add(f"{acell}.info.yaml")

    # 3) Get the projects (this used to be in Snakefile.report)
    L.debug(f"Will look into {len(yaml_info_files)} cells")
    for yif in yaml_info_files:
        try:
            plist.extend(find_projects_from_yaml(yif))
        except KeyError:
            L.warning(f"No ws_project in {yif} - indicates no 5-digit project name in readset XML")

    # And that is that
    return plist

def main():
    verbose = (os.environ.get("VERBOSE") or "0") != "0"
    L.basicConfig(level=(L.DEBUG if verbose else L.WARNING), stream=sys.stderr)

    plist = set(list_the_projects())
    print( *sorted(plist), sep='\n' )

if __name__  == '__main__':
    main()
