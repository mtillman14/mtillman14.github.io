#!/usr/bin/env zsh
#
# Updates the research output (talk map, publications, talks) for the website.
#
# Before running this script:
#   1. Publications: update your ORCID profile (ID set in site_updater/OrcidToBib.py).
#      Only ORCID works that have a BibTeX citation attached are pulled in.
#   2. Talks: add any new talks to site_updater/talks.csv (title, type,
#      url_slug, venue, date as YYYY-MM-DD, location, talk_url, authors, presenter, link_url).
#      presenter is only needed when the first author didn't present.
#      Put any talk PDFs in files/<type>/ with the same name as the generated .md file.
#   3. Activate a Python environment with the packages in site_updater/requirements.txt. First time:
#        python3 -m venv .venv && source .venv/bin/activate && pip install -r site_updater/requirements.txt
#      After that: `source .venv/bin/activate`
#   4. Make sure you have an internet connection. The script queries the ORCID API
#      (publications) and the Nominatim geocoder (talk map locations).
#   5. Run it from the root folder of the project (e.g. `./update_research_output.zsh`).
#
# After the updates, the script builds and serves the site locally with Jekyll
# (requires Ruby + `bundle install`, see README.md). Open http://localhost:4000 to check
# the results, press Ctrl-C to stop the server, then commit and push. On push, the GitHub
# Action (.github/workflows/pages.yml) rebuilds the CV PDF from the committed files and
# deploys the site, so files/cv.pdf itself isn't committed.

# Stop at the first failing step (e.g. ORCID unreachable) instead of carrying on
set -e

cd site_updater

# Update the output.bib file using works from ORCID
python OrcidToBib.py

# Update the .md files for the publications from the .bib file
python pubsFromBib.py

# Update the talks from the _talks/ folder (not from ORCID).
python talks.py

# Update the talkmap
python talkmap.py

# Build the CV from the markdown files (writes site_updater/cv/build/cv.tex,
# and files/cv.pdf if latexmk is installed, for the local preview)
python build_cv.py

# Build the site and serve it locally for review
cd ..
bundle exec jekyll serve -l -H localhost
