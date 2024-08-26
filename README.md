## SMRTino

Automatic processing and reporting for PacBio SMRT Cell data.

This is indended to complement the reports in SMRTLink. In particular there is a BLAST-based
contamination check and also some summary metrics, and notification of progress to RT.

Ideally I'd like to integrate this more closely with the SMRTLink reports, but at least we
can now link directly to them. It's a little tricky but possible with the right API calls.

SMRTino includes a simple Python wrapper for making API calls to SMRTLink.
