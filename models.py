import json
from math import cos, degrees, fabs, radians, sin
from pathlib import Path

import ezdxf
from colorfield.fields import ColorField
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.validators import FileExtensionValidator
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from djgeojson.fields import GeometryCollectionField, PointField
from filebrowser.base import FileObject
from filebrowser.fields import FileBrowseField
from PIL import ImageColor

from .utils import cad2hex, check_wide_image

User = get_user_model()


class Drawing(models.Model):

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="user_drawing",
        verbose_name=_("Author"),
    )
    title = models.CharField(
        _("Name"),
        help_text=_("Name of the drawing"),
        max_length=50,
    )
    intro = models.CharField(_("Description"), null=True, max_length=200)
    fb_image = FileBrowseField(
        _("Image"),
        max_length=200,
        extensions=[".jpg", ".png", ".jpeg", ".gif", ".tif", ".tiff"],
        directory="images/drawing/",
        null=True,
    )
    image = models.ImageField(
        _("Image"),
        max_length=200,
        null=True,
        upload_to="uploads/images/drawing/",
    )
    dxf = models.FileField(
        _("DXF file"),
        max_length=200,
        upload_to="uploads/djeocad/dxf/",
        validators=[
            FileExtensionValidator(
                allowed_extensions=[
                    "dxf",
                ]
            )
        ],
    )
    geom = PointField(_("Location"))
    rotation = models.FloatField(
        _("Rotation"),
        default=0,
    )
    private = models.BooleanField(
        _("Private drawing"),
        default=False,
    )

    __original_dxf = None
    __original_geom = None
    __original_rotation = None

    class Meta:
        verbose_name = _("Drawing")
        verbose_name_plural = _("Drawings")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__original_dxf = self.dxf
        self.__original_geom = self.geom
        self.__original_rotation = self.rotation

    def __str__(self):
        return self.title

    @property
    def popupContent(self):
        url = reverse(
            "djeocad:drawing_detail",
            kwargs={"username": self.user.username, "pk": self.id},
        )
        title_str = '<h5><a href="%(url)s">%(title)s</a></h5>' % {
            "title": self.title,
            "url": url,
        }
        intro_str = "<small>%(intro)s</small>" % {"intro": self.intro}
        image = self.get_thumbnail_path()
        if not image:
            return {"content": title_str + intro_str}
        image_str = '<img src="%(image)s">' % {"image": image}
        return {"content": title_str + image_str + intro_str}

    def get_thumbnail_path(self):
        if not self.fb_image:
            return
        path = self.fb_image.version_generate("popup").path
        return settings.MEDIA_URL + path

    def save(self, *args, **kwargs):
        # save and eventually upload image file
        super(Drawing, self).save(*args, **kwargs)
        if self.image:
            # image is saved on the front end, passed to fb_image and deleted
            self.fb_image = FileObject(str(self.image))
            self.image = None
            super(Drawing, self).save(*args, **kwargs)
            check_wide_image(self.fb_image)
        if (
            self.__original_dxf != self.dxf
            or self.__original_geom != self.geom
            or self.__original_rotation != self.rotation
        ):
            self.drawing_layer.all().delete()
            self.extract_dxf()

    def transform_vertices(self, vert):
        #  following conditional for test to work
        if isinstance(self.geom, str):
            self.geom = json.loads(self.geom)
        trans = []
        gy = 1 / (6371 * 1000)
        gx = 1 / (6371 * 1000 * fabs(cos(radians(self.geom["coordinates"][1]))))
        for v in vert:
            # use temp variables
            x = v[0]
            y = v[1]
            rot = radians(self.rotation)
            # get true north
            xr = x * cos(rot) - y * sin(rot)
            yr = x * sin(rot) + y * cos(rot)
            # objects are very small with respect to earth, so our transformation
            # from CAD x,y coords to latlong is approximate
            long = self.geom["coordinates"][0] + degrees(xr * gx)
            lat = self.geom["coordinates"][1] + degrees(yr * gy)
            trans.append([long, lat])
        return trans

    def extract_dxf(self):
        doc = ezdxf.readfile(Path(settings.MEDIA_ROOT).joinpath(str(self.dxf)))
        msp = doc.modelspace()
        # prepare layer table
        layer_table = {}
        for layer in doc.layers:
            layer_table[layer.dxf.name] = {
                "color": cad2hex(layer.color),
                "linetype": layer.dxf.linetype,
                "geometries": [],
            }
        # extract lines
        for e in msp.query("LINE"):
            points = [e.dxf.start, e.dxf.end]
            vert = self.transform_vertices(points)
            layer_table[e.dxf.layer]["geometries"].append(
                {
                    "type": "LineString",
                    "coordinates": vert,
                }
            )
        # extract polylines
        for e in msp.query("LWPOLYLINE"):
            vert = self.transform_vertices(e.vertices_in_wcs())
            if e.is_closed:
                vert.append(vert[0])
                layer_table[e.dxf.layer]["geometries"].append(
                    {
                        "type": "Polygon",
                        "coordinates": [vert],
                    }
                )
            else:
                layer_table[e.dxf.layer]["geometries"].append(
                    {
                        "type": "LineString",
                        "coordinates": vert,
                    }
                )
        # extract circles
        for e in msp.query("CIRCLE"):
            vert = self.transform_vertices(e.flattening(0.1))
            layer_table[e.dxf.layer]["geometries"].append(
                {
                    "type": "Polygon",
                    "coordinates": [vert],
                }
            )
        # extract arcs
        for e in msp.query("ARC"):
            vert = self.transform_vertices(e.flattening(0.1))
            layer_table[e.dxf.layer]["geometries"].append(
                {
                    "type": "LineString",
                    "coordinates": vert,
                }
            )
        # create Layers
        for name, layer in layer_table.items():
            if not layer["geometries"] == []:
                Layer.objects.create(
                    drawing_id=self.id,
                    name=name,
                    color_field=layer["color"],
                    geom={
                        "geometries": layer["geometries"],
                        "type": "GeometryCollection",
                    },
                )

    def get_file_to_download(self):
        doc = ezdxf.new()
        drw_layers = self.drawing_layer.all()
        for drw_layer in drw_layers:
            if drw_layer.name != "0":
                doc_layer = doc.layers.add(drw_layer.name)
            else:
                doc_layer = doc.layers.get("0")
            color = ImageColor.getcolor(drw_layer.color_field, "RGB")
            doc_layer.rgb = color
        path = Path(settings.MEDIA_ROOT).joinpath("uploads/djeocad/download.dxf")
        doc.saveas(filename=path, encoding="utf-8", fmt="asc")


class Layer(models.Model):

    drawing = models.ForeignKey(
        Drawing,
        on_delete=models.CASCADE,
        related_name="drawing_layer",
        verbose_name=_("Drawing"),
    )
    name = models.CharField(
        _("Layer name"),
        max_length=50,
    )
    color_field = ColorField(default="#FF0000")
    geom = GeometryCollectionField(_("Elements"))

    class Meta:
        verbose_name = _("Layer")
        verbose_name_plural = _("Layers")

    def __str__(self):
        return self.name + "-" + str(self.id)

    @property
    def popupContent(self):
        title_str = "<h6>%(layer)s: %(title)s</h6>" % {
            "layer": _("Layer"),
            "title": self.name,
        }
        return {"content": title_str, "color": self.color_field}
