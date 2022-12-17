window.addEventListener("map:init", function (event) {
    var map = event.detail.map; // Get reference to map
    point = JSON.parse(document.getElementById("locate_drawing").textContent);
    map.setView( [point.coordinates[1], point.coordinates[0]] , 19 );
  });
