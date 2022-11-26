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
    });

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

  const layer_control = L.control.layers(null).addTo(map);

  function getCollections() {
    // add eventually inactive base layers so they can be removed
    base_map.addTo(map);
    sat_map.addTo(map);
    // remove all layers from layer control and from map
    map.eachLayer(function (layer) {
      layer_control.removeLayer(layer);
      map.removeLayer(layer);
    });
    // add base layers back to map and layer control
    base_map.addTo(map);
    layer_control.addBaseLayer(base_map, "Base");
    layer_control.addBaseLayer(sat_map, "Satellite");
    // add other layers to map and layer control
    let collection = JSON.parse(document.getElementById("author_data").textContent);
    for (author of collection) {
      window[author] = L.layerGroup().addTo(map);
      layer_control.addOverlay(window[author], author);
    }
    // let mk_layer = L.layerGroup().addTo(map);
    let ln_layer = L.layerGroup().addTo(map);
    layer_control.addOverlay(mk_layer, "Markers");
    layer_control.addOverlay(ln_layer, "lines");
    // add objects to layers
    collection = JSON.parse(document.getElementById("marker_data").textContent);
    for (marker of collection.features) {
      L.geoJson(marker, {onEachFeature: onEachFeature}).addTo(window[marker.properties.popupContent.layer]);
    }
    // let markers = L.geoJson(collection, {onEachFeature: onEachFeature});
    // markers.addTo(mk_layer);
    map.fitBounds(L.geoJson(collection).getBounds(), {padding: [30,30]});
    collection = JSON.parse(document.getElementById("line_data").textContent);
    let lines = L.geoJson(collection, {style: setLineStyle, onEachFeature: onEachFeature});
    lines.addTo(ln_layer);
    collection = JSON.parse(document.getElementById("block_data").textContent);
    let blocks = L.geoJson(collection, {style: setLineStyle, onEachFeature: onEachFeature});
    blocks.addTo(ln_layer);
  }

  getCollections()

  addEventListener("refreshCollections", function(evt){
    getCollections();
  })
}
