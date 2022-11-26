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
    collection = JSON.parse(document.getElementById("layer_data").textContent);
    if (collection !== null) {
      for (layer_name of collection) {
        let name = "Layer - " + layer_name
        window[name] = L.layerGroup().addTo(map);
        layer_control.addOverlay(window[name], name);
      }
    }
    // add objects to layers
    collection = JSON.parse(document.getElementById("marker_data").textContent);
    for (marker of collection.features) {
      L.geoJson(marker, {onEachFeature: onEachFeature}).addTo(window[marker.properties.popupContent.layer]);
    }
    map.fitBounds(L.geoJson(collection).getBounds(), {padding: [30,30]});
    collection = JSON.parse(document.getElementById("line_data").textContent);
    if (collection !== null) {
      for (line of collection.features) {
        let name = "Layer - " + line.properties.popupContent.layer
        L.geoJson(line, {style: setLineStyle, onEachFeature: onEachFeature}).addTo(window[name]);
      }
    }
    // let lines = L.geoJson(collection, {style: setLineStyle, onEachFeature: onEachFeature});
    // lines.addTo(ln_layer);
    collection = JSON.parse(document.getElementById("block_data").textContent);
    if (collection !== null) {
      for (block of collection.features) {
        let name = "Layer - " + block.properties.popupContent.layer
        L.geoJson(block, {style: setLineStyle, onEachFeature: onEachFeature}).addTo(window[name]);
      }
    }
    // let blocks = L.geoJson(collection, {style: setLineStyle, onEachFeature: onEachFeature});
    // blocks.addTo(ln_layer);
  }

  getCollections()

  addEventListener("refreshCollections", function(evt){
    getCollections();
  })
}
