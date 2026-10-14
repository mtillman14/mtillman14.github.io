
# coding: utf-8

# # Talks markdown generator for academicpages
# 
# Takes a TSV of talks with metadata and converts them for use with [academicpages.github.io](academicpages.github.io). This is an interactive Jupyter notebook ([see more info here](http://jupyter-notebook-beginner-guide.readthedocs.io/en/latest/what_is_jupyter.html)). The core python code is also in `talks.py`. Run either from the `markdown_generator` folder after replacing `talks.tsv` with one containing your data.
# 
# TODO: Make this work with BibTex and other databases, rather than Stuart's non-standard TSV format and citation style.

# In[1]:

import json
import os

import pandas as pd


# ## Data format
# 
# The CSV needs to have the following columns: title, type, url_slug, venue, date, location, talk_url, authors, presenter, link_url, with a header at the top. Many of these fields can be blank, but the columns must be in the TSV.
# 
# - Fields that cannot be blank: `title`, `url_slug`, `date`. All else can be blank. `type` defaults to "Talk" 
# - `date` must be formatted as YYYY-MM-DD.
# - `presenter` is only needed when the first author didn't present (e.g. "Dr. Ambike"). The site and the CV both show
#   "<type> presentation by <presenter>", built from these fields, so the .md files don't need a description.
# - `url_slug` will be the descriptive part of the .md file and the permalink URL for the page about the paper. 
#     - The .md file will be `YYYY-MM-DD-[url_slug].md` and the permalink will be `https://[yourdomain]/talks/YYYY-MM-DD-[url_slug]`
#     - The combination of `url_slug` and `date` must be unique, as it will be the basis for your filenames
# 


# ## Import CSV
# 
# Pandas makes this easy with the read_csv function.

# In[3]:

talks = pd.read_csv("talks.csv")
talks


# ## Quote strings for YAML
# 
# Values are written as plain text in double-quoted YAML strings (JSON strings are valid YAML), so quotes and
# ampersands need no HTML entities.

# In[4]:

def yaml_str(text):
    return json.dumps(str(text), ensure_ascii=False)


# ## Creating the markdown files
# 
# This is where the heavy lifting is done. This loops through all the rows in the TSV dataframe, then starts to concatentate a big string (```md```) that contains the markdown for each type. It writes the YAML metadata; the page body is left empty.

# In[5]:

loc_dict = {}

for row, item in talks.iterrows():
    
    md_filename = str(item.date) + "-" + item.url_slug + ".md"
    html_filename = str(item.date) + "-" + item.url_slug 
    year = item.date[:4]
    
    md = "---\ntitle: " + yaml_str(item.title) + "\n"
    md += "collection: talks" + "\n"
    
    if len(str(item.type)) > 3:
        md += "type: " + yaml_str(item.type) + "\n"
    else:
        md += 'type: "Talk"\n'
    
    md += "permalink: /talks/" + html_filename + "\n"
    
    if len(str(item.venue)) > 3:
        md += "venue: " + yaml_str(item.venue) + "\n"
        
    md += "date: " + str(item.date) + "\n"
    
    if len(str(item.location)) > 3:
        md += "location: " + yaml_str(item.location) + "\n"
           
    if len(str(item.authors)) > 3:
        md += "authors: " + yaml_str(item.authors) + "\n"

    if len(str(item.presenter)) > 3:
        md += "presenter: " + yaml_str(item.presenter) + "\n"

    # The "Open Link to View" button on the site uses link_url. Fall back to talk_url, then to a PDF in files/<type>/
    link_url = ""
    if len(str(item.link_url)) > 3:
        link_url = item.link_url
    elif len(str(item.talk_url)) > 3:
        link_url = item.talk_url
    elif os.path.exists(os.path.join(os.path.dirname(os.getcwd()),'files',item.type.lower(),md_filename.replace('.md','.pdf'))): # Has file
        link_url = f"/files/{item.type.lower()}/{md_filename.replace('.md','.pdf')}"
    if link_url:
        md += "link_url: " + yaml_str(link_url) + "\n"

    md += "---\n"

    md_path = "../_talks/" + os.path.basename(md_filename)

    # In an existing file, the YAML fields generated from the CSV are updated in place (or added at the
    # end of the header if missing). Fields that aren't from the CSV (e.g. cv_note, cv_section), the
    # markdown body, and the line endings are left alone. Blank CSV cells don't remove a field.
    # A new file gets the full generated header and an empty body.
    if os.path.exists(md_path):
        with open(md_path, 'rb') as f:
            raw = f.read().decode('utf-8')
        newline = '\r\n' if '\r\n' in raw else '\n'
        _, header, body = raw.replace('\r\n', '\n').split('---\n', 2)
        generated = {line.split(':', 1)[0]: line for line in md[len("---\n"):-len("---\n")].strip('\n').split('\n')}
        lines = []
        for line in header.rstrip('\n').split('\n'):
            key = line.split(':', 1)[0] if ':' in line and not line[:1].isspace() else None
            lines.append(generated.pop(key) if key in generated else line)
        lines.extend(generated.values())
        md = "---\n" + "\n".join(lines) + "\n---\n"
        print("Updating header of", md_path)
    else:
        newline = '\n'
        body = ""
        print("Creating", md_path)

    with open(md_path, 'w', encoding='utf-8', newline=newline) as f:
        f.write(md + body)


# These files are in the talks directory, one directory below where we're working from.

