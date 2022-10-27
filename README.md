# django-geocad
Django app that imports CAD drawings in Leaflet maps
## Overview
Show CAD drawings with no geo location in interactive web maps. Change / add layers to drawings, change / add elements to layers.
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
