---
layout: single
title:  "Setting up the Website"
header:
  teaser: "unsplash-gallery-image-2-th.jpg"
categories: 
  - Jekyll
tags:
  - edge case
---
# Works
1. To make OrcidToBib.ipynb properly generate the output.bib file, the "citation" field of the work must be filled in on orcid.org using the Bibtex format. If not, it won't be properly added to the output.bib file. The Bibtex formatted citation can be found by right clicking the item in Zotero with the Better Bibtex plugin installed, and clicking "copy bibtex to clipboard".

2. Use the PubsFromBib.ipynb to convert the .bib file to the .md files that will be rendered on the website. Note that by default you will get an error about a missing `pkg_resources` package. Run `pip install setuptools` to fix this.

In the `publist` dictionary definition, comment out the "proceeding" key. Change the value of `["journal"]["file"]` to `output.bib`.

Also, by default this .ipynb file does not work because it does not create a "category" field, which is required for the publication to be listed.
