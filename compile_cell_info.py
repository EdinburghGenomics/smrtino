#!/usr/bin/env python3
import os, sys, re
import logging as L
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter

from statistics import stdev, mean
from zipfile import ZipFile
from smrtino import load_yaml, dump_yaml
from smrtino.ParseXML import get_metadata_info2, get_sts_info
import json

""" The info needed to report on a SMRT cell consists of several YAML files:
        sc_data.yaml about the files in the upstream
        unassigned.yaml about the unassigned reads (if applicable)
        bc1.yaml bc2.yaml about the barcodes.

    This super-simple script just outputs a file linking to these other files.
"""

REPORTS_IN_ZIP = "raw_data adapter ccs control loading".split()

def main(args):

    L.basicConfig(level=(L.DEBUG if args.debug else L.WARNING), stream=sys.stderr)

    # Load the JSON files from reports.zip. No interpretation is made yet.
    json_reports = load_reports_zip(vars(args))

    # Info from metadata.xml gets folded into these reports. get_metadata_info2()
    # does some interpretation and returns a single dict.
    if args.metaxml:
        metadata_xml_info = get_metadata_info2(args.metaxml)
    else:
        metadata_xml_info = None

    if args.stsxml:
        sts_xml_info = get_sts_info(args.stsxml)
    else:
        sts_xml_info = None

    # Due to the possibility of re-demultiplexing, we want to get the barcode metrics
    # form this report file.
    lima_counts = None
    if args.lima_counts:
        lima_counts = load_lima_counts(args.lima_counts)

    # Build the links to the files.
    info = gen_info(args)

    if args.extract_ids:
        if metadata_xml_info:
            # FIXME - actually there may be, because if we are re-running on the results
            # of manual de-multiplexing in SMRTLink then potentially the ws_name and ws_desc
            # could change? But how much do we care?
            exit("There's no point in using -x if we are loading metadata.xml directly.")
        info.update(extract_ids_multi(args.bcfiles))

    if json_reports:
        info.update(compile_json_reports( json_reports,
                                          metadata_xml = metadata_xml_info,
                                          sts_xml = sts_xml_info,
                                          lima_counts = lima_counts ))

    dump_yaml(info, fh=sys.stdout)

def load_reports_zip(args_dict):
    """Load the various JSON files directly from reports.zip. If any --foo_report
       is specified that takes precedence.
       Pass args as a dict to make testing this function a tad easier.
    """
    res = {}
    if args_dict.get('reports_zip'):
        with ZipFile(args_dict['reports_zip']) as repzip:
            for r in REPORTS_IN_ZIP:
                json_file = f"{r}.report.json"
                try:
                    with repzip.open(json_file) as jfh:
                        res[r] = json.load(jfh)
                except KeyError:
                    # For barcodes.report.json this is expected on unbarcoded runs
                    # but we don't look for that one any more.
                    L.warning(f"{json_file} was not found in {args_dict['reports_zip']}")

    # Now the individual files, if any
    for r in REPORTS_IN_ZIP:
        if args_dict.get(f'{r}_report'):
            with open(args_dict[f'{r}_report']) as jfh:
                if r in res:
                    L.warning(f"Overiding {r}.report.json from {args_dict['reports_zip']}"
                              f" with {args_dict[f'{r}_report']}")
                res[r] = json.load(jfh)

    return res

def compile_json_reports(reports_dict, metadata_xml, sts_xml=None, lima_counts=None):
    """This attempts to aggregate all the per-cell QC items wanted for the sign-off
       spreadsheet. The results will be arranged in a dictionary mimicking the current
       spreadsheet headings.

       We also bring in info from metadata_xml and sts_xml.
    """
    reports = { 'Run': {},
                'Sample Loaded': {},
                'Raw Data': {},
                'Loading': {},
                'HiFi Data': {},
                'HiFi Length %': {},
                'Hifi Quality %': {},
                'Barcodes': {},
                'Control': {},
                'Adapter': {},
                'Instrument': {},
                'Dataset': {} }

    # Let's load it up. This will be a long function.
    reports['Run']['Movie Time (hours)'] = metadata_xml['movie_time']
    reports['Run']['Library type'] = metadata_xml['application'] # Maybe?
    reports['Run']['Adaptive loading'] = "{}".format(metadata_xml['adaptive_loading'])
    reports['Run']['SMRT Cell Lot Number'] = metadata_xml['smrt_cell_lot_number']
    reports['Run']['Well Sample Name'] = metadata_xml['ws_name']
    reports['Run']['Well name'] = metadata_xml['run_slot']
    reports['Run']['Run started'] = metadata_xml['run_start']

    # This stuff is to be found in {cell}.sample-setup.yaml but as this has to
    # be fetched with an API query we're going to fold it in at the make_report.py
    # stage. Insert Size does get copied to the metadata.xml file though.
    reports['Sample Loaded']['Application'] = None
    reports['Sample Loaded']['Insert size (bp)'] = int(metadata_xml['insert_size'])
    reports['Sample Loaded']['Sample Concentration (ng/µl)'] = None
    reports['Sample Loaded']['Sample Concentration (nM)'] = None
    reports['Sample Loaded']['Sample Volume to Use (µl)'] = None
    reports['Sample Loaded']['Concentration after clean-up (ng/ul)'] = None
    reports['Sample Loaded']['% of  recovery (anticipated)'] = None
    reports['Sample Loaded']['% of  recovery (real)'] = "to be calculated"

    # This is coming from reports_dict['raw_data']
    rd = { a['id']: a['value'] for a in reports_dict['raw_data']['attributes'] }
    reports['Raw Data']['Polymerase Read Bases (Gb)'] = "{:.1f}".format(rd['raw_data_report.nbases'] / 1e9)
    reports['Raw Data']['Polymerase Reads (M)'] = "{:.1f}".format(rd['raw_data_report.nreads'] / 1e6)
    reports['Raw Data']['Polymerase Read N50'] = "{}".format(rd['raw_data_report.read_n50'])
    reports['Raw Data']['Longest Subread N50'] = "{}".format(rd['raw_data_report.insert_n50'])
    reports['Raw Data']['Unique Molecular Yield (Gb)'] = "{:.1f}".format(rd['raw_data_report.unique_molecular_yield'] / 1e9)

    # This one from reports_dict['loading'], aside from OPLC which we don't have
    ld = { v['id']: v['value'] for v in reports_dict['loading']['attributes'] }
    productive_zmws = ld['loading_xml_report.productive_zmws']
    for n in ["0", "1", "2"]:
        if productive_zmws:
            productivity_pct = (ld[f'loading_xml_report.productivity_{n}_n'] / productive_zmws) * 100
            reports['Loading'][f'P{n} %'] = "{:.2f}".format(productivity_pct)
        else:
            reports['Loading'][f'P{n} %'] = "0.0"

    reports['Loading']['OPLC (pM), On-Plate Loading Conc.'] = metadata_xml['on_plate_loading_conc']
    reports['Loading']['Real OPLC (pM), after clean-up'] = "to be calculated"

    # This is under reports_dict['ccs'] and yes these really are HiFi numbers
    ccsd = { a['id']: a['value'] for a in reports_dict['ccs']['attributes'] }
    reports['HiFi Data']['HiFi Reads (M)'] = "{:.2f}".format(ccsd['ccs2.number_of_ccs_reads'] / 1e6)
    reports['HiFi Data']['HiFi Yield (Gb)'] = "{:.2f}".format(ccsd['ccs2.total_number_of_ccs_bases'] / 1e6)
    reports['HiFi Data']['HiFi Read Length (mean, bp)'] = "{}".format(ccsd['ccs2.mean_ccs_readlength'])
    reports['HiFi Data']['HiFi Read Length (median, bp)'] = "{}".format(ccsd['ccs2.median_ccs_readlength'])
    reports['HiFi Data']['HiFi Read Quality (median)'] = ccsd['ccs2.median_accuracy']
    reports['HiFi Data']['HiFi Bases Quality ≥Q30 (%)'] = "{:.2f}".format(ccsd['ccs2.percent_ccs_bases_q30'] * 100)
    reports['HiFi Data']['HiFi Number of Passes (mean)'] = "{}".format(ccsd['ccs2.mean_npasses'])

    # Shred two tables from the reports_dict['ccs'] section
    try:
        ccst1, = [ t['columns'] for t in reports_dict['ccs']['tables']
                   if t['id'] == 'ccs2.hifi_length_summary' ]
        ccsd1 = dict(zip(*[c['values'] for c in ccst1 if c['id'] == 'ccs2.hifi_length_summary.read_length'],
                         *[c['values'] for c in ccst1 if c['id'] == 'ccs2.hifi_length_summary.reads_pct']))
        reports['HiFi Length %']['≥ 5,000 bp'] = "{:.1f}".format(ccsd1['≥ 5,000'])
        reports['HiFi Length %']['≥ 10,000 bp'] = "{:.1f}".format(ccsd1['≥ 10,000'])
        reports['HiFi Length %']['≥ 15,000 bp'] = "{:.1f}".format(ccsd1['≥ 15,000'])
        reports['HiFi Length %']['≥ 20,000 bp'] = "{:.1f}".format(ccsd1['≥ 20,000'])

        ccst2, = [ t['columns'] for t in reports_dict['ccs']['tables']
                   if t['id'] == 'ccs2.read_quality_summary' ]
        ccsd2 = dict(zip(*[c['values'] for c in ccst2 if c['id'] == 'ccs2.read_quality_summary.read_qv'],
                         *[c['values'] for c in ccst2 if c['id'] == 'ccs2.read_quality_summary.reads_pct']))
        reports['Hifi Quality %']['≥ Q30'] = "{:.1f}".format(ccsd2['≥ Q30'])
        reports['Hifi Quality %']['≥ Q40'] = "{:.1f}".format(ccsd2['≥ Q40'])
    except ValueError:
        reports['HiFi Length %']['all'] = "missing table in JSON"
        reports['Hifi Quality %']['all'] = "missing table in JSON"

    # Barcodes
    if lima_counts:
        reports['Barcodes'].update(summarize_lima_counts(lima_counts))
    elif 'barcodes' in reports_dict:
        # This is problematic because we don't get a fresh report if the run is re-demultiplexed
        bcd = { a['id']: a['value'] for a in reports_dict['barcodes']['attributes'] }

        # This just for the CV - Surely this is already logged somewhere?
        bct, = [t for t in reports_dict['barcodes']['tables'] if t['id'] == "barcode.barcode_table"]
        bcvq, = [c for c in bct['columns'] if c['id'] == "barcode.barcode_table.mean_bcqual"]
        bcvc, = [c for c in bct['columns'] if c['id'] == "barcode.barcode_table.number_of_reads"]

        reports['Barcodes']['Number of samples'] = bcd['barcode.n_barcodes']
        reports['Barcodes']['Assigned Reads (%)'] = "{:.2f}".format(bcd['barcode.percent_barcoded_reads'] * 100)
        reports['Barcodes']['CV'] = "{:.2f}".format(calculate_cv(bcvc['values'], bcvq['values']))
    else:
        reports['Barcodes']['Number of samples'] = 0 # As distinct from a single barcoded sample
        reports['Barcodes']['Assigned Reads (%)'] = 100
        reports['Barcodes']['CV'] = "N/A"

    # Control
    cond = { a['id']: a['value'] for a in reports_dict['control']['attributes'] }
    reports['Control']['Number of Control Reads'] = "{}".format(cond['control.reads_n'])
    reports['Control']['Control Read Length Mean'] = "{:.0f}".format(cond['control.readlength_mean'])
    reports['Control']['Control Read Concordance Mean'] = "{:.3f}".format(cond['control.concordance_mean'])
    reports['Control']['Control Read Concordance Mode'] = "{:.3f}".format(cond['control.concordance_mode'])

    # Adapter
    reports['Adapter']['Local Base Rate'] = "unknown"
    if sts_xml:
        reports['Adapter']['Adapter Dimers (0-10bp) %'] = "{:.4f}".format(sts_xml['adapter_dimers'])
        reports['Adapter']['Short Inserts (11-100bp) %'] = "{:.4f}".format(sts_xml['short_inserts'])
        reports['Adapter']['Local Base Rate'] = "{:.2f}".format(sts_xml['local_base_rate_median'])
    elif 'adapter' in reports_dict:
        adad = { a['id']: a['value'] for a in reports_dict['adapter']['attributes'] }
        reports['Adapter']['Adapter Dimers (0-10bp) %'] = "{:.2f}".format(adad['adapter_xml_report.adapter_dimers'])
        reports['Adapter']['Short Inserts (11-100bp) %'] = "{:.2f}".format(adad['adapter_xml_report.short_inserts'])
        reports['Adapter']['Local Base Rate'] = "{:.2f}".format(adad['adapter_xml_report.local_base_rate_median'])

    # Instrument
    reports['Instrument']['Run ID'] = metadata_xml['run_id']
    reports['Instrument']['Instrument SN'] = metadata_xml['instrument_id']
    reports['Instrument']['Instrument Control SW Version'] = metadata_xml['version_ics']
    reports['Instrument']['Instrument Chemistry Bundle Version'] = metadata_xml['version_chemistry']
    reports['Instrument']['Primary SW Version'] = metadata_xml['version_smrtlink']

    # Dataset
    reports['Dataset']['Movie ID'] = metadata_xml['cell_id']
    reports['Dataset']['Well Sample Name'] = metadata_xml['ws_name']
    reports['Dataset']['Cell ID'] = metadata_xml['smrt_cell_label_number']

    # This is funky, as the metadata.xml is full of dates but the JSON reports only have them
    # in the comments. I don't want to look at the timestamps of the files.
    mo = re.search(r"at ([-0-9]{10})T[0-9:.]+", reports_dict['ccs']['_comment'])
    reports['Dataset']['Data created'] = mo.group(1)

    # That's it! But I need to add back some info that was previously handled by extract_ids_multi
    basic_fields = "run_id run_slot cell_id cell_uuid ws_name ws_desc".split()
    return dict( reports = reports,
                 **{ k: metadata_xml[k] for k in basic_fields } )

def load_lima_counts(filename):
    """Load a lima_counts.txt file and return a dict of {barcode: n}
       Unassigned reads will have the barcode of 'unassigned'
    """
    res = dict()

    with open(filename) as fh:
        # Standard TSV loading
        try:
            headers = next(fh).rstrip("\n").split("\t")
        except StopIteration:
            # File was completely empty. This is ok.
            pass

        for aline in fh:
            line_as_dict = dict(zip(headers, aline.rstrip("\n").split("\t")))

            if line_as_dict['IdxCombinedNamed'] == "Not Barcoded":
                bc_name = "unassigned"
            else:
                bc_name = f"{line_as_dict['IdxCombinedNamed']}--{line_as_dict['IdxCombinedNamed']}"

            res[bc_name] = int(line_as_dict['Counts'])

    return res

def summarize_lima_counts(lima_counts):
    """Summarize the lima_counts, assuming this was actually a barcoded run.
    """
    unassigned = lima_counts['unassigned']
    assigned = [v for k, v in lima_counts.items() if k != 'unassigned']
    if len(assigned) > 1:
        cov = stdev(assigned) / mean(assigned)
    else:
        cov = 0.0

    return { 'Number of samples': len(assigned),
             'Assigned Reads (%)': "{:.2f}".format(sum(assigned) * 100 / (sum(assigned) + unassigned)),
             'CV': "{:.2f}".format(cov) }

def calculate_cv(counts_list, qual_list):
    """Calculate the CV of counts_list. If qual_list is provided I'll use it to spot the non-barcoded
       sample which has qual 0.0. I could just assume it's always the last sample, but I want a sanity
       check.
    """
    if qual_list:
        if len([q for q in qual_list if q == 0.0]) != 1:
            raise RuntimeError(f"dodgy qual_list: {qual_list}")
        counts_list = [ p[0] for p in zip(counts_list, qual_list) if p[1] != 0.0 ]

    if mean(counts_list) < 1:
        return "NaN"
    else:
        return stdev(counts_list) / mean(counts_list)

def extract_ids_multi(yaml_files):
    """Run extract_ids() on each of the YAML files and verify that
       the result is the same in all cases, and return the resulting dict.

       If the info is being extracted directly from the metadata.xml file
       this function is pointless and -x option should not be used.
    """
    # FIXME - for the reason above this should probably be removed.
    extracted_ids = extract_ids(yaml_files[0])

    for yf in yaml_files[1:]:
        alt_ids = extract_ids(yf)

        if alt_ids != extracted_ids:
            raise RuntimeError(f"extract_ids({yaml_files[0]}) mismatch with extract_ids({yf}):\n"
                               f"{extracted_ids}\nvs\n{alt_ids}")

    return extracted_ids


def extract_ids(yaml_file):
    """Pull some bits needed for link_to_smrtlink.py
    """
    ydata = load_yaml(yaml_file)

    return { k: ydata[k]
             for k in '''run_id run_slot cell_id cell_uuid
                         ws_name ws_desc'''.split() }

def gen_info(args):

    res = dict()
    for k in ['sc_data', 'unassigned']:
        v = getattr(args, k)
        if v and v != "-":
            res[k] = check_exists(v, args.check_yaml)

    # If args.extract_ids is set then there's no point in loading the YAML twice.
    check_bcfile_yaml = args.check_yaml and (not args.extract_ids)
    res['barcodes'] = [ check_exists(f, check_bcfile_yaml) for f in args.bcfiles ]

    return res

def check_exists(f, syntax_check=True):
    """Check that a file exists. In fact, check it's valid YAML
    """
    if syntax_check:
        load_yaml(f)
    else:
        assert os.path.exists(f)

    return '@' + f

def parse_args(*args):
    description = """Provide XML for the various bits of report.
                  """
    argparser = ArgumentParser( description=description,
                                formatter_class = ArgumentDefaultsHelpFormatter )
    argparser.add_argument("bcfiles", nargs='*',
                            help="Info YAML files to be linked per barcode")
    argparser.add_argument("--sc_data",
                            help="Location of sc_data.yaml for the cell")
    argparser.add_argument("--unassigned",
                            help="Location of info.yaml for unassigned reads")

    argparser.add_argument("--reports_zip",
                            help="Location of reports.zip for this cell")
    for r in REPORTS_IN_ZIP:
        argparser.add_argument(f"--{r}_report",
                                help=f"Explicitly add/override {r}.report.json for this cell")

    argparser.add_argument("--metaxml",
                            help="Location of metadata.xml for this cell")
    argparser.add_argument("--stsxml",
                            help="Location of sts.xml for this cell")
    argparser.add_argument("--lima_counts",
                            help="Location of lima_counts.txt for this cell")

    argparser.add_argument("-d", "--debug", action="store_true",
                            help="Print more verbose debugging messages.")
    argparser.add_argument("-c", "--check_yaml", action="store_true",
                            help="Check that the YAML files can be loaded.")
    argparser.add_argument("-x", "--extract_ids", action="store_true",
                            help="Add the run_id, cell_id, cell_uuid, ws_name from the info files")

    return argparser.parse_args(*args)


if __name__ == "__main__":
    main(parse_args())
