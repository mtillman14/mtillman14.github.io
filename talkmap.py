

# # Leaflet cluster map of talk locations
#
# (c) 2016-2017 R. Stuart Geiger, released under the MIT license
#
# Run this from the _talks/ directory, which contains .md files of all your talks. 
# This scrapes the location YAML field from each .md file, geolocates it with
# geopy/Nominatim, and uses the getorg library to output data, HTML,
# and Javascript for a standalone cluster map.
#
# Requires: glob, getorg, geopy

import time
import os
import glob
import getorg
from geopy import Nominatim
from geopy.exc import GeocoderInsufficientPrivileges, GeocoderUnavailable, GeocoderTimedOut

os.chdir('_talks') # Navigate to the _talks directory

g = glob.glob("*.md")


# geocoder = Nominatim(user_agent="myGeocoder")
geocoder = Nominatim(user_agent="talkmap@mtillman14.github.io")
location_dict = {}
location = ""
permalink = ""
title = ""


for file in g:
    print(file)
    with open(file, 'r') as f:
        lines = f.read()
        if lines.find('location: "') > 1:
            loc_start = lines.find('location: "') + 11
            lines_trim = lines[loc_start:]
            loc_end = lines_trim.find('"')
            location = lines_trim[:loc_end]

        if location == "Virtual":
            continue
                                       
        try:
            time.sleep(1)  # To respect Nominatim's usage policy
            location_dict[location] = geocoder.geocode(location)
        except GeocoderInsufficientPrivileges:
            print(f"GeocoderInsufficientPrivileges error -- skipping location: {location}")
            continue
        except GeocoderUnavailable:
            print(f"GeocoderUnavailable error -- skipping location: {location}")
            continue
        except GeocoderTimedOut:
            print(f"GeocoderTimedOut error -- skipping location: {location}")
            continue

        print(location, "\n", location_dict[location])


m = getorg.orgmap.create_map_obj()
getorg.orgmap.output_html_cluster_map(location_dict, folder_name="../talkmap", hashed_usernames=False)

os.chdir('..') # Navigate back to the main directory


