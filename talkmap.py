

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

geocoder = Nominatim(user_agent="talkmap@mtillman14.github.io")
location_dict = {}
location = ""
permalink = ""
title = ""


def get_locations(g: list) -> tuple:
    location_dict = {}
    venue_dict = {}  # Map location -> set of venues
    for file in g:
        print(file)
        with open(file, 'r') as f:
            lines = f.read()
            location = ""
            venue = ""

            if lines.find('location: "') > 1:
                loc_start = lines.find('location: "') + 11
                lines_trim = lines[loc_start:]
                loc_end = lines_trim.find('"')
                location = lines_trim[:loc_end]

            if lines.find('venue: "') > 1:
                ven_start = lines.find('venue: "') + 8
                lines_trim = lines[ven_start:]
                ven_end = lines_trim.find('"')
                venue = lines_trim[:ven_end]

            if not location or location == "Virtual":
                continue

            if location not in venue_dict:
                venue_dict[location] = set()
            if venue:
                venue_dict[location].add(venue)

            if location in location_dict:
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
    return location_dict, venue_dict


location_dict, venue_dict = get_locations(g)
m = getorg.orgmap.create_map_obj()
getorg.orgmap.output_html_cluster_map(location_dict, folder_name="../talkmap", hashed_usernames=False)


def add_venues_to_org_locations(venue_dict):
    """Post-process org-locations.js to add venue as a 4th element in each array."""
    js_path = os.path.join('..', 'talkmap', 'org-locations.js')
    with open(js_path, 'r') as f:
        content = f.read()

    import json
    # Parse the JS array from the file
    start = content.find('[')
    end = content.rfind(']') + 1
    data = json.loads(content[start:end])

    # Add venue to each entry
    for entry in data:
        location = entry[0]
        venues = venue_dict.get(location, set())
        entry.append(", ".join(sorted(venues)) if venues else "")

    # Write back
    with open(js_path, 'w') as f:
        f.write("var addressPoints = " + json.dumps(data, indent=2) + ";\n")


add_venues_to_org_locations(venue_dict)

# Post-process the generated map.html to customize it
def customize_map_html():
    map_path = os.path.join('..', 'talkmap', 'map.html')
    with open(map_path, 'r') as f:
        content = f.read()
    
    # Modify the script tag in the body
    # Find the start of the script tag
    script_start = content.find('<script type="text/javascript">')
    if script_start == -1:
        return
    
    # Find the end of the script tag
    script_end = content.find('</script>', script_start)
    if script_end == -1:
        return
    
    # Get the parts before and after the script
    before_script = content[:script_start]
    after_script = content[script_end + 9:] # 9 is length of '</script>'
    
    # Define your custom script here
    custom_script = '''
            var tiles = L.tileLayer('http://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}', {
            maxZoom: 18,
            attribution: 'Tiles &copy; Esri &mdash; Source: Esri, DeLorme, NAVTEQ, USGS, Intermap, iPC, NRCAN, Esri Japan, METI, Esri China (Hong Kong), Esri (Thailand), TomTom, 2012'
        });

        var latlng = L.latLng(30, 10);
        var map = L.map('map', {center: latlng, zoom: 0.7, layers: [tiles]});

        var markers = L.markerClusterGroup({
            showCoverageOnHover: false,
            maxClusterRadius: 80
        });

        for (var i = 0; i < addressPoints.length; i++) {
            var a = addressPoints[i];
            var title = a[0];
            var venue = a[3];
            var marker = L.marker(new L.LatLng(a[1], a[2]), { title: title });
            marker.bindPopup("<b>" + title + "</b><br>" + venue);
            markers.addLayer(marker);
        }

        map.addLayer(markers);
        map.zoomIn();'''
    
    # Combine the parts with the custom script
    new_content = before_script + '<script type="text/javascript">' + custom_script + '</script>' + after_script
    
    # Write the modified content back to the file
    with open(map_path, 'w') as f:
        f.write(new_content)

# Run the customization
customize_map_html()

os.chdir('..') # Navigate back to the main directory


