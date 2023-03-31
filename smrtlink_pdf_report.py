#!/usr/bin/env python3

"""Generate and save a PDF report for a single SMRT cell by calling
   the SMRTLink API.
"""

import os, sys
import logging as L
from time import sleep, time
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter

from smrtino.SMRTLink import SMRTLinkClient, HTTPError

class StopWatch:
    """A class that tells you how long since it was initiated.
    """
    def __init__(self):
        self._start_time = time()

    def __call__(self):
        return time() - self._start_time

def main(args):

    L.basicConfig(level=(L.DEBUG if args.debug else L.INFO))

    # Resolve the report name which may have {cell_uuid} in there
    out_file = args.out_file.format(cell_uuid=args.cell_uuid)

    if args.rc_section == 'none':
        L.warning("Running in no-connection mode as rc_section==none")
        # Bypass API connection for testing and just make an empty report
        with open(out_file, 'wb') as __:
            pass

    # Ask the API to generate the report. Just one at a time.
    conn = SMRTLinkClient.connect_with_creds(section=args.rc_section)
    post_body = dict(ids=[args.cell_uuid])
    L.debug(f"Requesting job-manager/jobs/make-dataset-reports with body {post_body}")
    try:
        post_res = conn.post_endpoint('/smrt-link/job-manager/jobs/make-dataset-reports', post_body)
    except HTTPError as e:
        if e.response.status_code == 422:
            L.exception("Status 422 normally indicates that the cell_uuid is not in SMRTLink")
            if args.empty_on_missing:
                L.warning("Saving empty report as --empty_on_missing is set")
                with open(out_file, 'wb') as __:
                    pass
                return
            else:
                raise
        else:
            raise

    # From this we can build an endpoint prefix for the following calls
    job_endpoint = f"/smrt-link/job-manager/jobs/{post_res['jobTypeId']}/{post_res['uuid']}"

    # Poll the API until the job completes (or fails)
    L.info(f"Waiting up to {args.timeout} seconds for job {post_res['uuid']}")
    elapsed = StopWatch()
    poll_state = 'none'
    while elapsed() < args.timeout:
        poll_res = conn.get_endpoint(job_endpoint)
        poll_state = poll_res['state']
        L.debug(f"State of job after {int(elapsed())} seconds is {poll_state}")
        if poll_state in ['CREATED', 'SUBMITTED', 'RUNNING']:
            # We wait
            sleep(args.poll_interval)
        else:
            break

    if poll_state != 'SUCCESSFUL':
        # Either we timed out or we entered a failed state. Either way, we quit.
        exit(f"Reporting job is in state {poll_state} after {int(elapsed())} seconds. Giving up.")

    # Now we should have a report, so let's download it. Assume there is always one PDF for this job.
    ds_res = conn.get_endpoint(f"{job_endpoint}/datastore")
    pdf_uuid = [d['uuid'] for d in ds_res if d['fileTypeId'] == 'PacBio.FileTypes.pdf' ][0]

    L.info(f"Saving PDF report to {out_file}")
    conn.download_endpoint(f"{job_endpoint}/datastore/{pdf_uuid}/download", dest_file=out_file)


def parse_args(*args):
    description = """Given a cell UUID, request SMRTLink to make a PDF report for that
                     cell, wait for the report to be ready, and then download and save
                     the report.
                     Connection to the API is as per ~/.smrtlinkrc
                  """
    argparser = ArgumentParser( description=description,
                                formatter_class = ArgumentDefaultsHelpFormatter )
    argparser.add_argument("--rc_section", default=os.environ.get("SMRTLINKRC_SECTION", "smrtlink"),
                            help="Read specified section in .smrtlinkrc for connection details")
    argparser.add_argument("--timeout", type=int, default=(5*60),
                            help="Number of seconds to wait before deciding the report is not coming")
    argparser.add_argument("--poll_interval", type=int, default=5,
                            help="Number of seconds to wait between polls to the API")
    argparser.add_argument("-o", "--out_file", default="{cell_uuid}.pdf",
                           help="Name of the PDF file to be saved")
    argparser.add_argument("--empty_on_missing", action="store_true",
                            help="Save an empty file if SMRTLink does not recognise the run."
                                 " Only really useful within Snakemake to avoid halting the workflow.")


    argparser.add_argument("cell_uuid",
                           help="UUID of the cell to report on")

    argparser.add_argument("-d", "--debug", action="store_true",
                            help="Print more verbose debugging messages.")

    return argparser.parse_args(*args)

if __name__ == "__main__":
    main(parse_args())
