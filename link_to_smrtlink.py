#!/usr/bin/env python3

""" API caller wrapper to discover links to SMRTLink
"""

import os, sys
import logging as L
import yaml
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter

from smrtino.SMRTLink import SMRTLinkClient

""" I want to return something like...

'run_dir': 'r64175e_20220401_133539',
'smrtlink_run_uuid': 'dfb8647e-eb3e-4b6c-9351-92930fb6f058',
'smrtlink_run_name': 'Run 04.01.2022 12:28',
'smrtlink_run_link': 'https://smrtlink.genepool.private:8243/sl/run-qc/dfb8647e-eb3e-4b6c-9351-92930fb6f058',
'cell_dir' : 'm64175e_220401_135226',
'cell_uuid' : 'x-x-x-x',
'cell_type' : 'ccsreads',
'smrtlink_cell_link' : 'https://smrtlink.genepool.private:8243/sl/data-management/dataset-detail/130fcef7-4c88-46aa-8026-016c1b9ee2e8?type=ccsreads'

"""
conn = None

def main(args):

    L.basicConfig(level=(L.DEBUG if args.debug else L.WARNING))

    # Load that YAML file
    with open(args.info_yml) as yfh:
        info_yml = yaml.safe_load(yfh)

    res = dict( run_dir = info_yml['run_id'],
                cell_dir = info_yml['cell_id'],
                cell_uuid = info_yml.get('cell_uuid'),
                cell_type = info_yml.get('_readset_type') )

    if args.rc_section == 'none':
        L.warning("Running in no-connection mode as rc_section==none")
        # Test mode!
        res['smrtlink_cell_link'] = 'https://test.example.com/cell'
        res['smrtlink_run_link'] = 'https://test.example.com/run'
        res['smrtlink_run_name'] = 'test run'
        res['smrtlink_run_uuid'] = '0-0-0-0-0'
        yaml.safe_dump(res, sys.stdout)
        return

    # Simplest connection with ~/.smrtlinkrc defaults
    global conn
    conn = SMRTLinkClient.connect_with_creds(section=args.rc_section)

    # We need to query the API for the 'smrtlink_run_name' so may as well get the 'cell_uuid'
    # and 'cell_type' as well, even though we already have them in the XML.
    L.debug("Querying the API for cell type and UUID")
    try:
        cell_res = get_cell_id_and_type(res['cell_dir'], uuid=res['cell_uuid'])

        # If we do have 'cell_uuid' and '_readset_type' in the info.yml then sanity check that
        # everything matches.
        for k, v in cell_res.items():
            info_v = res.get(k)
            if info_v and (info_v != v):
                raise RuntimeError(f"Value for {k} in info.yml is {info_v} but SMRTLink says {v}")
        # Once happy, fold in the new values
        res.update(cell_res)

        # Having sorted that out, get the run UUID which we always have to go to the API for as
        # it's not in the XML at all.
        res['smrtlink_run_uuid'] = get_run_uuid(res['run_dir'], res['smrtlink_run_name'])

        # Now we have to fill in smrtlink_run_link and smrtlink_cell_link
        host_for_links = args.link_host or conn.link_host
        res.update(make_links(res, host_for_links))
    except RuntimeError:
        L.exception("Failed to get all the info from SMRTLink")
        # But we still dump what we have

    # And print the result
    yaml.safe_dump(res, sys.stdout)

def make_links(res, host):
    """Make some links. Pretty simple
    """
    return dict( smrtlink_cell_link = f"{host}/sl/data-management/dataset-detail/{res['cell_uuid']}?type={res['cell_type']}",
                 smrtlink_run_link  = f"{host}/sl/run-qc/{res['smrtlink_run_uuid']}", )

def get_cell_id_and_type(cell_dir, uuid=None):
    """Get some info about the cell from the API.
       We can do this without fetching every cell because the datasets endpoint supports search
       by 'metadataContextId'.
       However, this will also see derived datasets, so you can provide uuid as a hint to
       find the right one.
       Return a dict with keys {'cell_uuid', 'cell_type', 'smrtlink_run_name'}
    """
    # TODO - check this works for CLR reads, I only tested it for CCS.
    all_cells = []
    for dstype in ['ccsreads', 'subreads']:
        dsets = conn.get_endpoint(f"/smrt-link/datasets/{dstype}", metadataContextId=cell_dir)
        L.debug(f"Found {len(dsets)} matching cells in {dstype}")
        for c in dsets:
            c['_dstype'] = dstype
            all_cells.append(c)

    L.debug(f"Fetched total of {len(all_cells)} cells")

    # If the filter failed, we may have records we don't want?
    all_cells = [ c for c in all_cells if c['metadataContextId'] == cell_dir ]

    # Remove anything with the 'barcoded' tag??
    #all_cells = [ c for c in all_cells if 'barcoded' not in c['tags'].split(',') ]

    # If a uuid is supplied then also filter on that
    if uuid:
        all_cells = [ c for c in all_cells if c['uuid'] == uuid ]

    if not all_cells:
        raise RuntimeError(f"No cell found for {cell_dir}")
    elif len(all_cells) > 1:
        # We see this for cells like 'm64175e_220527_152717' which are demultiplexed into
        # separate CCS sub-datasets. The filter on c['tags'] should sort this but for now I'll
        # also take the last in the list, which is the first record.
        L.warning(f"Multiple records found for cell {cell_dir}")

    cell = all_cells[-1]
    return dict( cell_uuid = cell['uuid'],
                 cell_type = cell['_dstype'],
                 smrtlink_run_name = cell['runName'] )

def get_run_uuid(run_dir, run_name=None):
    """Get the UUID associated with a run (and thus the QC report) by the run directory name.
       You also should provide the run name, as returned by get_cell_id_and_type(), because
       the API does not support a direct search by 'context' so without this we need to fetch
       all runs and filter.
    """
    if run_name:
        all_runs = conn.get_endpoint("/smrt-link/runs", name=run_name)
    else:
        # OK fetch them all
        all_runs = conn.get_endpoint("/smrt-link/runs")
    L.debug(f"Fetched all {len(all_runs)} runs")

    # Filter the results, in any case
    my_run = [ r for r in all_runs if r['context'] == run_dir ]

    if not my_run:
        raise RuntimeError(f"No run found for {run_dir}")
    elif len(my_run) > 1:
        raise RuntimeError(f"Multiple records found for {run_dir}")

    return my_run[0]['uniqueId']


def parse_args(*args):
    description = """Takes a .info.yml file and call the SMRTLink API to discover
                     appropriate links to the Run QC and Dataset. Dumps the result
                     in YAML format.
                     Connection to the API is as per ~/.smrtlinkrc
                  """
    argparser = ArgumentParser( description=description,
                                formatter_class = ArgumentDefaultsHelpFormatter )
    argparser.add_argument("--link_host",
                            help="Force hostname on links to be different from that in .smrtlinkrc")
    argparser.add_argument("--rc_section", default=os.environ.get("SMRTLINKRC_SECTION", "smrtlink"),
                            help="Read specified section in .smrtlinkrc for connection details")

    argparser.add_argument("info_yml",
                           help=".info.yml file produced by compile_cell_info.py")

    argparser.add_argument("-d", "--debug", action="store_true",
                            help="Print more verbose debugging messages.")

    return argparser.parse_args(*args)

if __name__ == "__main__":
    main(parse_args())
