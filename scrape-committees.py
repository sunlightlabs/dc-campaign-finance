import math
import re
import time

from lxml import html
from pyquery import PyQuery as pq
import requests
import unicodecsv as csv

URL = "http://ocf.dc.gov/registration_statements/pcc/pcc_searchresult.asp"

#
# configure requests session
#

headers = {'User-Agent': 'sunlightlabs/dc-campaign-finance'}
session = requests.Session()
session.headers = headers

#
# find total candidate count
#

resp = session.get(URL)

matches = re.findall(r"Total Records : (\d+)", resp.content)

total = int(matches[0])
per_page = 20
pages = int(math.ceil(float(total) / per_page))

#
# scrape all the pages
#

count = 0

with open('data/committee-candidate.csv', 'w') as outfile:

    writer = csv.writer(outfile)
    writer.writerow(('committee', 'candidate'))

    for page in list(p + 1 for p in range(pages)):

        print "page %d" % page

        params = {
            'ftype': 'PCC',
            'whichpage': page,
            'DelCnt': total,
            # the following don't really matter
            'SQL_Order_by': '',
            'SQL_sort': '',
            'reg_comm_name': '',
            'ele_year': '',
            'reg_first_name': '',
            'reg_last_name': '',
            'mode_value': '',
        }

        resp = session.post(URL, params)

        doc = html.fromstring(resp.content)
        d = pq(doc)

        rows = d("form[name=pcc_searchresult]").find("table").find('tr')

        for row in rows[8:28]:

            cols = pq(row).find('td')

            committee = pq(cols[1]).text()
            candidate = pq(cols[0]).text()

            if committee != 'N/A':
                writer.writerow((committee, candidate))

            count += 1

            if count >= total:
                break

        time.sleep(0.5)
