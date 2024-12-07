---
layout: single
title:  "Setting up this website from template"
# categories: 
#   - Jekyll
tags:
  - documentation
---
Setting up this personal website from the template at [academic pages](https://github.com/academicpages/academicpages.github.io) involves several steps:
1. Set up localhost using ruby so that the website can be served for development.
2. Setting up the markdown generator .ipynb files to fill in Publications from ORCID and Talks from a .csv file. Also add the corresponding PDF files for the Publications and Poster Talks.

# Localhost
[The academic pages template](https://github.com/academicpages/academicpages.github.io) instructions provide instructions to run the site on localhost. On MacOS, by default the command `gem install bundler` fails because the user doesn't have permissions to override the system Ruby install. To overcome this issue, follow these steps:

1. Run `which ruby`. If it returns `/usr/bin/ruby` that means the system ruby install is being used, which is causing the failure.

2. Add the following to the profile `~/.zshrc`: 
```bash
eval "$(/opt/homebrew/bin/brew shellenv)"
export PATH="/opt/homebrew/opt/ruby/bin:$PATH"
export PATH="`gem env gemdir`/bin:$PATH"
```

3. Reload the shell with `source ~/.zshrc` and verify that the ruby version has changed by running `which ruby`, which should now return `/opt/homebrew/opt/ruby/bin/ruby`.

4. Now, running `gem install bundler` should succeed.

5. To serve the site on `localhost:4000`, run `jekyll serve -l -H localhost`.

# Pages
## Publications
1. To make OrcidToBib.ipynb properly generate the output.bib file, the "citation" field of the work must be filled in on orcid.org using the Bibtex format. If not, it won't be properly added to the output.bib file. The Bibtex formatted citation can be found by right clicking the item in Zotero with the Better Bibtex plugin installed, and clicking "copy bibtex to clipboard".

2. Use the PubsFromBib.ipynb to convert the .bib file to the .md files that will be rendered on the website. Note that by default you will get an error about a missing `pkg_resources` package. Run `pip install setuptools` to fix this.

In the `publist` dictionary definition, comment out the "proceeding" key. Change the value of `["journal"]["file"]` to `output.bib`.

Also, by default this .ipynb file does not work because it does not create a "category" field, which is required for the publication to be listed.
Valid "category" fields appear to be `manuscripts` for a "Journal Articles" title, `conferences` for a "Conference Presentations" title.

I also added the `paperurl` field. Unfortunately right now I have to manually add the PDF files. Maybe could be automated from Zotero in the future.

## Talks
1. Create a new `talks.csv` file and populate it with all of the talks given. For the url slug, I just used the abbreviation of the venue.
2. Run all of the cells.

## CV
1. I added my CV PDF file to files/cv.pdf. I added a download link to _pages/cv.md.