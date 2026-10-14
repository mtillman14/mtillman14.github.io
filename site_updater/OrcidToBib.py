import sys

import requests

orcid = '0000-0002-3115-1587'
API = 'https://pub.orcid.org/v3.0/{}'.format(orcid)
HEADERS = {"Accept": "application/orcid+json"}


def get(path):
    """GET an ORCID API path, stopping with a clear message on network or HTTP errors."""
    try:
        response = requests.get(API + path, headers=HEADERS, timeout=30)
        response.raise_for_status()
    except requests.RequestException as e:
        sys.exit(f"ORCID request failed ({e}); output.bib was not changed.")
    return response.json()


record = get('/works')
put_codes = [work['work-summary'][0]['put-code'] for work in record['group']]

citations = []
for put_code in put_codes:
    work = get('/work/{}'.format(put_code))
    if work['citation'] is not None:
        citations.append(work['citation']['citation-value'])

# Only overwrite output.bib once every request has succeeded
if not citations:
    sys.exit("ORCID returned no works with a BibTeX citation; output.bib was not changed.")

# author list, title, publication venue, vol/issue/page/year, doi
with open('output.bib', 'w') as bibfile:
    for citation in citations:
        bibfile.write(citation)
        bibfile.write('\n')
print(f"Wrote {len(citations)} citations to output.bib")
