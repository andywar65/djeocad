# django-geocad 1.2.0
Django app that imports CAD drawings in Leaflet maps
## Overview
Show CAD drawings with no geo location in interactive web maps. Change / add layers to drawings, change / add elements to layers, download changed DXF files.
## Requirements
This app is tested on Django 4.1 and Python 3.10.0. It relies on [django-leaflet](https://django-leaflet.readthedocs.io/en/latest/index.html/) as map engine, [django-geojson](https://django-geojson.readthedocs.io/en/latest/) for storing geodata, [django-filebrowser](https://django-filebrowser.readthedocs.io/en/latest/) for managing pictures, [ezdxf](https://ezdxf.mozman.at/) for for handling DXF files, [django-colorfield](https://github.com/fabiocaccamo/django-colorfield) for admin color fields and [django-htmx](https://django-htmx.readthedocs.io/en/latest/) for interactions. I use [Bootstrap 5](https://getbootstrap.com/) for styling. I develop this app inside my personal [starter project](https://github.com/andywar65/project_repo/tree/architettura) that provides all the libraries you need, along with an authentication engine. If you want to embed `django-geocad` into your project you will need to make some tweaks.
## Installation
In your project root type `git clone https://github.com/andywar65/djeocad`, add `djeocad.apps.DjeocadConfig` to `INSTALLED_APPS` and `path(_('geocad/'), include('djeocad.urls', namespace = 'djeocad'))` to your project `urls.py`, migrate and collectstatic. You also need to add initial map defaults to `settings.py` (these are the settings for Rome, change them to your city of choice):
`LEAFLET_CONFIG = {
    "DEFAULT_CENTER": (41.8988, 12.5451),
    "DEFAULT_ZOOM": 10,
    "RESET_VIEW": False,
}`
If you want a satellite map layer you need a [Mapbox](https://www.mapbox.com/) token adding this to `settings.py` (I use `environs` for secrets):
`MAPBOX_TOKEN = env.str("MAPBOX_TOKEN")`
## Usage
Django-geocad has two models, `Drawing` and `Layer`. Creation, update and deletion of models happen
in admin, so you will need staff permission to perform these tasks. A `GeoCAD Manager` permission
group is created at migration, but at the moment the feature is not implemented.
To create a `Drawing` you will need a `DXF file` in ASCII format. `DXF` is a drawing exchange
format widely used in `CAD` applications.
If `geodata` is embedded in the file, it will be ignored: this app is suitable for small drawings,
representing a building, a group of buildings or a small neighborhood. To geolocate the drawing you just need to know where your `World Coordinate System` origin (0,0,0) is located. A good position for the `WCS` origin could be the cornerstone of a building, or another geographic landmark close to
the items of the drawing.
Check also the rotation of the `Y axis` with respect to the `True North`: it is typical to orient
the drawings most conveniently for drafting purposes, unrespectful of True North. Please note that positive angles (from Y axis to True North) are counter clockwise.
So back to our admin panel, let's add a Drawing. You will have to select the `Author` of the drawing,
a `Title`, a short description, an image and the `DXF file`. In the map select the location of your
`WCS origin`, then enter the `Rotation` (angle with respect to True North). Eventually check `Private` to prevent other users from viewing your drawing.
Press the `Save and continue` button. If all goes well the `DXF file` will be extracted and a list of `Layers` will be attached to your drawing. Each layer inherits the `Name` and color originally assigned in CAD. `ARC`, `CIRCLE`, `LINE` and `LWPOLYLINE` entities are visible on the map panel. It is possible to change layer name and layer entities.
## Outside of Admin
At this stage only three frontend views are implemented: `List of all drawings`, `List by author` and `Drawing Detail`. First two views show drawings as markers on the map, last one shows a drawing in detail, with layers displayed on the map. To access the `List of all drawings` search on the navigation bar for `Projects/GeoCAD`. Note that `private` drawings will be hidden from non authors in all views. Note also that all entities on a layer inherit layer color.
In `Drawing Detail` view it is possible to download back the (eventually modified) `DXF file`. Please note that `True North` will be respected, `ARC` and `CIRCLE` entities will be approximated to `LWPOLYLINES`, and `Layers` will have `True Colors` instead of `ACI Colors`.
## Changelog v1.2.0
* Extract ARC and CIRCLE entities
* Download drawings as DXF
## Further improvements
* Full CRUD on frontend
* Ability to switch single layers on/off in drawing detail view
* Extract blocks
