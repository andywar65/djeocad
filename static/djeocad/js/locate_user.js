window.addEventListener("map:init", function (event) {
    var map = event.detail.map; // Get reference to map
    map.locate().on('locationfound', userFound).on('locationerror', userNotFound);

    function userNotFound(e) {
      // alert(e.message);
    };

    function userFound(e) {
      map.setView( e.latlng , 19 );
    };

  });
