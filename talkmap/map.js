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
    var description = a[3]; // Add this if you want the extra field
    var marker = L.marker(new L.LatLng(a[1], a[2]), { title: title });
    marker.bindPopup("<b>" + title + "</b><br>" + description); // Modified for two lines
    markers.addLayer(marker);
}

map.addLayer(markers);
map.zoomIn();