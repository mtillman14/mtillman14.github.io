#!/usr/bin/env python
# coding: utf-8

# # Publications markdown generator for academicpages
# 
# Takes a set of bibtex of publications and converts them for use with [academicpages.github.io](academicpages.github.io). This is an interactive Jupyter notebook ([see more info here](http://jupyter-notebook-beginner-guide.readthedocs.io/en/latest/what_is_jupyter.html)). 
# 
# The core python code is also in `pubsFromBibs.py`. 
# Run either from the `markdown_generator` folder after replacing updating the publist dictionary with:
# * bib file names
# * specific venue keys based on your bib file preferences
# * any specific pre-text for specific files
# * Collection Name (future feature)
# 
# TODO: Make this work with other databases of citations, 
# TODO: Merge this with the existing TSV parsing solution


from pybtex.database.input import bibtex
import pybtex.database.input.bibtex 
from time import strptime
import string
import html
import json
import os
import re

#todo: incorporate different collection types rather than a catch all publications, requires other changes to template
publist = {
    # "proceeding": {
    #     "file" : "proceedings.bib",
    #     "venuekey": "booktitle",
    #     "venue-pretext": "In the proceedings of ",
    #     "category": "conferences",
    #     "collection" : {"name":"publications",
    #                     "permalink":"/publication/"}
        
    # },
    "journal":{
        "file": "output.bib",
        "venuekey" : "journal",
        "venue-pretext" : "",
        "category": "manuscripts",
        "collection" : {"name":"publications",
                        "permalink":"/publication/"}
    } 
}

def yaml_str(text):
    """Plain text as a double-quoted YAML string (JSON strings are valid YAML)."""
    return json.dumps(text, ensure_ascii=False)


for pubsource in publist:
    parser = bibtex.Parser()
    bibdata = parser.parse_file(publist[pubsource]["file"])

    #loop through the individual references in a given bibtex file
    for bib_id in bibdata.entries:
        #reset default date
        pub_year = "1900"
        pub_month = "01"
        pub_day = "01"
        
        b = bibdata.entries[bib_id].fields
        
        try:
            pub_year = f'{b["year"]}'

            #todo: this hack for month and day needs some cleanup
            if "month" in b.keys(): 
                if(len(b["month"])<3):
                    pub_month = "0"+b["month"]
                    pub_month = pub_month[-2:]
                elif(b["month"] not in range(12)):
                    tmnth = strptime(b["month"][:3],'%b').tm_mon   
                    pub_month = "{:02d}".format(tmnth) 
                else:
                    pub_month = str(b["month"])
            if "day" in b.keys(): 
                pub_day = str(b["day"])

                
            pub_date = pub_year+"-"+pub_month+"-"+pub_day
            
            #strip out {} as needed (some bibtex entries that maintain formatting)
            clean_title = b["title"].replace("{", "").replace("}","").replace("\\","").replace(" ","-")    

            url_slug = re.sub("\\[.*\\]|[^a-zA-Z0-9_-]", "", clean_title)
            url_slug = url_slug.replace("--","-")

            md_filename = (str(pub_date) + "-" + url_slug + ".md").replace("--","-")
            html_filename = (str(pub_date) + "-" + url_slug).replace("--","-")

            #Build Citation from text
            citation = ""

            #citation authors - todo - add highlighting for primary author?
            for author in bibdata.entries[bib_id].persons["author"]:
                citation = citation+" "+author.first_names[0]+" "+author.last_names[0]+", "

            #full author names as plain text (no HTML entities), used by build_cv.py
            authors = ", ".join(
                " ".join(author.first_names + author.middle_names + author.last_names).replace("{", "").replace("}", "")
                for author in bibdata.entries[bib_id].persons["author"])

            #display title: keep degree signs (e.g. 90{$^\circ$}) as °, then strip BibTeX braces/backslashes
            display_title = b["title"].replace("$^\\circ$", "°").replace("{", "").replace("}","").replace("\\","")

            #citation title
            citation = citation + "\"" + display_title + ".\""

            #add venue logic depending on citation type
            venue = publist[pubsource]["venue-pretext"]+b[publist[pubsource]["venuekey"]].replace("{", "").replace("}","").replace("\\","")

            citation = citation + " " + venue
            citation = citation + ", " + pub_year + "."

            
            ## YAML variables            
            md = "---\ntitle: " + yaml_str(display_title) + "\n"
            
            md += """collection: """ +  publist[pubsource]["collection"]["name"]

            #conference proceedings are often exported as @article; file them under conferences
            category = "conferences" if "proceeding" in venue.lower() else publist[pubsource]["category"]
            md += """\ncategory: """ + category

            md += """\npermalink: """ + publist[pubsource]["collection"]["permalink"]  + html_filename
            
            note = False
            if "note" in b.keys():
                if len(str(b["note"])) > 5:
                    md += "\nexcerpt: " + yaml_str(b["note"])
                    note = True

            md += "\ndate: " + str(pub_date) 

            md += "\nvenue: " + yaml_str(venue)
            
            md += "\nauthors: " + yaml_str(authors)

            # The "Download Paper" button uses paperurl: the .bib url if there is one, else a PDF in files/publications/
            url = False
            pdf_filename = md_filename.replace('.md', '.pdf')
            if "url" in b.keys() and len(str(b["url"])) > 5:
                md += "\npaperurl: " + yaml_str(b["url"])
                url = True
            elif os.path.exists(os.path.join("..", "files", "publications", pdf_filename)):
                md += f"\npaperurl: /files/publications/{pdf_filename}"

            md += "\ncitation: " + yaml_str(citation)

            md += "\n---"

            
            ## Markdown description for individual page
            if note:
                md += "\n" + b["note"] + "\n"

            if url:
                md += "\n[Access paper here](" + b["url"] + "){:target=\"_blank\"}\n" 
            else:
                md += "\nUse [Google Scholar](https://scholar.google.com/scholar?q="+html.escape(clean_title.replace("-","+"))+"){:target=\"_blank\"} for full citation"

            md_filename = os.path.basename(md_filename)

            md_path = "../_publications/" + md_filename

            # In an existing file, the YAML fields generated from the .bib are updated in place (or added at
            # the end of the header if missing). Other fields (e.g. location, type, doi), the markdown body,
            # and the line endings are left alone. A new file gets the full generated header and body.
            newline = "\n"
            if os.path.exists(md_path):
                with open(md_path, 'rb') as f:
                    raw = f.read().decode('utf-8')
                newline = '\r\n' if '\r\n' in raw else '\n'
                _, header, body = raw.replace('\r\n', '\n').split('---\n', 2)
                generated = {line.split(':', 1)[0]: line for line in md[len("---\n"):].split("\n---", 1)[0].split('\n')}
                lines = []
                for line in header.rstrip('\n').split('\n'):
                    key = line.split(':', 1)[0] if ':' in line and not line[:1].isspace() else None
                    lines.append(generated.pop(key) if key in generated else line)
                lines.extend(generated.values())
                md = "---\n" + "\n".join(lines) + "\n---\n" + body

            with open(md_path, 'w', encoding="utf-8", newline=newline) as f:
                f.write(md)
            print(f'SUCESSFULLY PARSED {bib_id}: \"', b["title"][:60],"..."*(len(b['title'])>60),"\"")
        # field may not exist for a reference
        except KeyError as e:
            print(f'WARNING Missing Expected Field {e} from entry {bib_id}: \"', b["title"][:30],"..."*(len(b['title'])>30),"\"")
            continue
