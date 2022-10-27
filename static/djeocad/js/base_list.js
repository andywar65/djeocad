function map_init(map, options) {

  function onEachFeature(feature, layer) {
    if (feature.properties && feature.properties.popupContent) {
      layer.bindPopup(feature.properties.popupContent.content, {minWidth: 256});
    }
  }

  function setLineStyle(feature) {
    return {"color": feature.properties.popupContent.color, "weight": 5 };
  }

  const base_map = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    {
      attribution: '',
      maxZoom: 19,
    }).addTo(map);

  const mapbox_token = JSON.parse(document.getElementById("mapbox_token").textContent);

  const sat_map = L.tileLayer("https://api.mapbox.com/styles/v1/{id}/tiles/{z}/{x}/{y}?access_token={accessToken}",
    {
      attribution: 'Imagery © <a href="https://www.mapbox.com/">Mapbox</a>',
      maxZoom: 19,
      tileSize: 512,
      zoomOffset: -1,
      id: "mapbox/satellite-v9",
      accessToken: mapbox_token
    });

  let mk_layer = L.layerGroup().addTo(map);
  let ln_layer = L.layerGroup().addTo(map);

  const baseMaps = {
    "Base": base_map,
    "Satellite": sat_map
  };

  const overlayMaps = {
    "Markers": mk_layer,
    "Drawings": ln_layer
  };

  L.control.layers(baseMaps, overlayMaps).addTo(map);

  let collection = JSON.parse(document.getElementById("marker_data").textContent);
  let markers = L.geoJson(collection, {onEachFeature: onEachFeature});
  markers.addTo(mk_layer);
  map.fitBounds(markers.getBounds(), {padding: [30,30]});
  collection = JSON.parse(document.getElementById("line_data").textContent);
  let lines = L.geoJson(collection, {style: setLineStyle, onEachFeature: onEachFeature});
  lines.addTo(ln_layer);

  addEventListener("getMarkerCollection", function(evt){
    mk_layer.clearLayers();
    ln_layer.clearLayers();
    let collection = JSON.parse(document.getElementById(evt.detail.value).textContent);
    let markers = L.geoJson(collection, {onEachFeature: onEachFeature});
    markers.addTo(mk_layer);
    map.fitBounds(markers.getBounds(), {padding: [30,30]});
  })

  addEventListener("getLineCollection", function(evt){
    let collection = JSON.parse(document.getElementById(evt.detail.value).textContent);
    let lines = L.geoJson(collection, {style: setLineStyle, onEachFeature: onEachFeature});
    lines.addTo(ln_layer);
  })
}
