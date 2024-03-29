# django-geocad 2.4.0
Django app that imports CAD drawings in Leaflet maps
## Overview
Show CAD drawings with no geo location in interactive web maps. Change / add layers to drawings, change / add elements to layers, change blocks and change / add it's instances, download changed DXF files with geo location.
## Requirements
This app is tested on Django 4.1 and Python 3.10.0. It heavily relies on outstanding [ezdxf](https://ezdxf.mozman.at/) for handling DXF files, [pyproj](https://pyproj4.github.io/pyproj/stable/) for geographic projections, [django-leaflet](https://django-leaflet.readthedocs.io/en/latest/index.html/) as map engine, [django-geojson](https://django-geojson.readthedocs.io/en/latest/) for storing geodata, [shapely](https://shapely.readthedocs.io/en/stable/manual.html) for polygon verification, [django-filebrowser](https://django-filebrowser.readthedocs.io/en/latest/) for managing pictures, [django-colorfield](https://github.com/fabiocaccamo/django-colorfield) for admin color fields and [django-htmx](https://django-htmx.readthedocs.io/en/latest/) to manage interactions. I use [Bootstrap 5](https://getbootstrap.com/) for styling. I develop this app inside my personal [starter project](https://github.com/andywar65/project_repo/tree/architettura) that provides all the libraries you need, along with an authentication engine. If you want to embed `django-geocad` into your project you will need to make some tweaks.
## Installation
See `requirements.in` for required libraries. In your project root type `git clone https://github.com/andywar65/djeocad`, add `djeocad.apps.DjeocadConfig` to `INSTALLED_APPS` and `path(_('geocad/'), include('djeocad.urls', namespace = 'djeocad'))` to your project `urls.py`, migrate and collectstatic. You also need to add initial map defaults to `settings.py` (these are the settings for Rome, change them to your city of choice):
`LEAFLET_CONFIG = {
    "DEFAULT_CENTER": (41.8988, 12.5451),
    "DEFAULT_ZOOM": 10,
    "RESET_VIEW": False,
}`
A satellite tile layer is expected, so you will need a [Mapbox](https://www.mapbox.com/) token to make it work. Add the token to `project/settings.py` (I use `environs` for secrets): `MAPBOX_TOKEN = env.str("MAPBOX_TOKEN")`.
Unauthenticated users can upload DXF files, but it's possible to limit the number of extracted entities by setting `DJEOCAD_MAX_ENTITIES = integer` (it is 20 by default).
## View drawings
On the navigation bar look for `Projects/GeoCAD`. You will be presented with a `List of all drawings` and a `List by author`, where drawings are just markers on the map. Click on a marker and follow the link in the popup: you will land on the `Drawing Detail` page, with layers displayed on the map. Layers may be switched on and off.
## Create drawings
Unauthenticated users can upload a drawing (to modify it see further paragraph). To create a `Drawing` you will need a `DXF file` in ASCII format. `DXF` is a drawing exchange format widely used in `CAD` applications.
If `geodata` is embedded in the file, the drawing will be imported in the exact geographical location. If `geodata` is unavailable, you will have to insert it manually: to geolocate the drawing you need to define a point on the drawing of known Latitude / Longitude. Mark the point on the map and insert it's coordinates with respect to DXF `World Coordinate System origin (0,0,0)`. A good position for the `Reference / Design point` could be the cornerstone of a building, or another geographic landmark nearby the entities of your drawing.
Check also the rotation of the drawing with respect to the `True North`: it is typical to orient the drawings most conveniently for drafting purposes, unrespectful of True North. Please note that in CAD counterclockwise rotations are positive, so if you have to rotate the drawing clockwise to orient it correctly, you will have to enter a negative angle.
Try to upload files with few entities at the building scale, as the conversion may be unaccurate for small items (units must be in meters).
Add a `Title` and a short description (if you are authenticated you can also check the drawing as `Private` to prevent other users from viewing it). The `Private` flag also unlimits the number of extracted entities.
Press the `Save` button. If all goes well the `DXF file` will be extracted and a list of `Layers` will be attached to your drawing. Each layer inherits the `Name` and color originally assigned in CAD. `POINT`, `ARC`, `CIRCLE`, `ELLIPSE`, `SPLINE`, `3DFACE`, `HATCH`, `LINE` and `LWPOLYLINE` entities are visible on the map panel, where they inherit layer color. If unnested `BLOCKS` are present in the drawing, they will be extracted and inserted on respective layer.
## Downloading
In `Drawing Detail` view it is possible to download back the (eventually modified) `DXF file`. Some limitations apply: curved entities will be approximated to `LWPOLYLINES`, `Layers` will have `True Colors` instead of `ACI Colors` and entities in blocks will all belong to layer `0`. Closed polylines will be transformed in hatches. On the other hand, `GeoData` will be associated to the `DXF`, so if you upload the file again, it will be automatically located on the map.
## Modify drawings
If you are authenticated and granted `GeoCAD Manager` permissions, you can modify the drawings you have personally uploaded.
You can modify the drawing `Title`, image and descripition, along with the `DXF` source file or geographic location / rotation. You can check the drawing as `Private` to prevent others from viewing it.
You can create, update and delete `Layers` associated to the drawing. You can access layer `Name`, color and linetype (continuous and dashed are the allowed types), and modify entity geometries. Some limitations occour: Layer `0` can't be deleted or renamed and you can't have duplicate layer names in the same drawing (that's consistent with CAD behaviour).
If you want to create a new `BLOCK`, make a `Layer` first, then transform it to block (an instance of the block will replace the layer). `Blocks` share the same model as `Layers`, so they can be modified. When updating a `Block` you will be able to access it's instances. Apart from normal CRUD operations, you can also `explode` an instance: the instance will be deleted, but it's entities will be transferred to insertion layer (this is common practice in CAD).
Beware that if a download is performed, the original file will be replaced with the downloaded copy, so you will eventually lose some data.
## About Geodata
Geodata can be stored in DXF, but `ezdxf` library can't deal with all kind of coordinate reference systems (CRS). If Geodata is not found in the file (or if the CRS is not compatible) `django-geocad` asks for user input: the location of a point both on the map and on the drawing coordinates system, and the rotation with respect to True North. The `pyproj` library hands over the best Universal Transverse Mercator CRS for the location (UTM is compatible with `ezdxf`). Thanks to UTM, Reference / Design Point and rotation input, Geodata can be built from scratch and incorporated into the file.

## Changelog v2.4.0
* Design point written in Geodata
## Changelog v2.3.0
* Change layers / blocks / instances from drawing detail
## Changelog v2.2.2
* Fixed recursion error on Layer delete
## Changelog v2.2.1
* Correct explanation of Rotation field
## Changelog v2.2.0
* Hatch support
* Correct geometry type in Leaflet.draw module
* Layer linetypes
## Changelog v2.1.0
* More entity types
## Changelog v2.0.0
* All transformations use `ezdxf` and `pyproj` methods
* `Geodata` are stored in downloaded file
## Changelog v1.6.1
* Fixed bug in drawing download
* Upload files without login
## Changelog v1.6.0
* Transform layer to block
* C*UD views need permissions
## Changelog v1.5.0
* CRUD of block instances
* Ability to switch single layers on/off in drawing detail view
## Changelog v1.4.0
* Extended CRUD on frontend
## Changelog v1.3.0
* Extract BLOCKS
## Changelog v1.2.0
* Extract ARC and CIRCLE entities
* Download drawings as DXF
## Further improvements
* Open to suggestions
