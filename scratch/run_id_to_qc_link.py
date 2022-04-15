#!/usr/bin/env python3

import sys, os
# Incantation for allowing scripts in subdirectories.
if __name__ == "__main__":
    sys.path.append( os.path.dirname(__file__) + "/..")

import readline
from pprint import pprint
from smrtino.SMRTLink import SMRTLinkClient

# Simplest connection with ~/.smrtlinkrc defaults
conn = SMRTLinkClient.connect_with_creds()

# Get the QC link for run r64175e_20220401_133539, or whatever is requested
runs_to_find = sys.argv[1:]
if not runs_to_find:
    runs_to_find.append("r64175e_20220401_133539")
    print(f"Looking for default run {runs_to_find[0]}")

def main():
    # This doesn't search. Maybe there's a way? Doc says I have to filter the results.
    # I can search by name but can't see way to search by "context".
    all_runs = conn.get_endpoint("/smrt-link/runs")

    for rtf in runs_to_find:

        my_run = [ r for r in all_runs if r['context'] == rtf ]

        if not my_run:
            print(f"Multiple records found for {rtf}")
        if len(my_run) > 1:
            print(f"No run found for {rtf}")
        else:
            print(f"QC report for {rtf}")

        for arun in my_run:
            # pprint(my_run)

            print(f"{conn.host}/sl/run-qc/{arun['uniqueId']}")

# Because I can search for runs by name, another option is to get the dataset (from any flowcell)
# then search for the run by name, rather than UUID. I don't know if the names are guaranteed to
# be unique, but I can filter the list by r['context'] == rtf anyway.

# Let's implement this.
def get_run_uuid(run_dir, cell_uuid=None, rstype=None):
    """Get the UUID associated with a run (and thus the QC report) by the run_name.
       If a cell_uuid is provided, it gives us a short cut to find the run without
       fetching all the runs and scanning the list.
       If rstype is provided, it saves yet another call to discover this info.
    """
    if cell_uuid:

        if not rstype:
            # Pre-fetch
            ds_by_uuid = conn.get_endpoint(f"/smrt-link/datasets/{cell_uuid}")

            # We need to get the more specific version
            rstype = {'ccs': 'ccsreads', 'subreads': 'subreads'}[ds_by_uuid['tags']]

        # And fetch again
        ds_by_uuid = conn.get_endpoint(f"/smrt-link/datasets/{rstype}/{cell_uuid}")

        # And now we should have the run name
        run_name = ds_by_uuid['runName']

        # Don't be tempted to put the query into the URL manually - this quotes run names
        # robustly.
        all_runs = conn.get_endpoint("/smrt-link/runs", name=run_name)
    else:
        # OK just fetch the lot
        # I feel there should be some secret search parameter, but I tried various options
        # with no joy.
        all_runs = conn.get_endpoint("/smrt-link/runs")

        print(f"Fetched all {len(all_runs)} runs")

    my_run = [ r for r in all_runs if r['context'] == run_dir ]

    if not my_run:
        raise RuntimeError(f"No run found for {run_dir}")
    elif len(my_run) > 1:
        raise RuntimeError(f"Multiple records found for {run_dir}")

    return my_run[0]['uniqueId']

def get_cell_uuid(cell_dir):
    """This is redundant cos we can get it from the XML
    """
    all_cells = conn.get_endpoint(f"/smrt-link/datasets/ccsreads", metadataContextId=cell_dir)
    print(f"Fetched all {len(all_cells)} cells")

    return [ c for c in all_cells if c['metadataContextId'] == cell_dir ]



#uuid = get_run_uuid(runs_to_find[0], cell_uuid='130fcef7-4c88-46aa-8026-016c1b9ee2e8')
uuid = get_run_uuid(runs_to_find[0])
exit(repr(uuid))

pprint(get_cell_uuid('m64175e_220401_135226'))
exit(0)

def ge(url):
    pprint(conn.get_endpoint(url))

main()
readline.add_history('ge("smrt-link/run-qc")')
import pdb ; pdb.set_trace()

