#!/usr/bin/env python3
import requests

# Can I extract a plot from a SMRTLink report? Maybe by scraping the HTML, maybe by finding the file in the backend?
# Or is there an API call I can do?

url_to_scrape = 'https://smrtlink.genepool.private:8243/sl/data-management/dataset-detail/260e6336-6ab3-4476-92d7-492bd2348249?type=ccsreads&show=plot-raw_data_report-raw_data_report.base_yield_plot_group'

# Let's do a naive fetch. This will fail cos we're not authenticated.

r = requests.get(url_to_scrape, auth=('user', 'pass'), timeout=4, verify=False)

print(r.status_code)

print(r.text)


