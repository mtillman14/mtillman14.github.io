# Run this script from the root folder of the project to update all the files for the website.

# Update the talkmap
python talkmap.py

# Update the output.bib file using works from ORCID
python markdown_generator/OrcidToBib.py

# Update the .md files for the publications from the .bib file
python markdown_generator/PubsFromBib.py

# Update the talks from the _talks/ folder (not from ORCID).
python markdown_generator/talks.py