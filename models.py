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
    needs_refresh = models.BooleanField(
        _("Refresh DXF file from layers"),
        default=True,
        editable=False,
    )

    __original_dxf = None
    __original_geom = None
    __original_rotation = None
    gy = 1 / (6371 * 1000)
    name_blacklist = ["*Model_Space", "DynamicInputDot"]

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
            self.related_layers.all().delete()
            self.extract_dxf()

    def xy2latlong(self, vert):
        trans = []
        gx = self.gy * 1 / (fabs(cos(radians(self.geom["coordinates"][1]))))
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
            lat = self.geom["coordinates"][1] + degrees(yr * self.gy)
            trans.append([long, lat])
        return trans

    def b_xy2latlong(self, vert):
        trans = []
        gx = self.gy
        for v in vert:
            # use temp variables
            xr = v[0]
            yr = v[1]
            # objects are very small with respect to earth, so our transformation
            # from CAD x,y coords to latlong is approximate
            long = degrees(xr * gx)
            lat = degrees(yr * self.gy)
            trans.append([long, lat])
        return trans

    def extract_dxf(self):
        #  following conditional for test to work
        if isinstance(self.geom, str):
            self.geom = json.loads(self.geom)
        doc = ezdxf.readfile(Path(settings.MEDIA_ROOT).joinpath(str(self.dxf)))
        msp = doc.modelspace()
        # prepare layer table
        layer_table = {}
        for layer in doc.layers:
            if layer.rgb:
                color = cad2hex(layer.rgb)
            else:
                color = cad2hex(layer.color)
            layer_table[layer.dxf.name] = {
                "color": color,
                "linetype": layer.dxf.linetype,
                "geometries": [],
            }
        # extract lines
        for e in msp.query("LINE"):
            points = [e.dxf.start, e.dxf.end]
            vert = self.xy2latlong(points)
            layer_table[e.dxf.layer]["geometries"].append(
                {
                    "type": "LineString",
                    "coordinates": vert,
                }
            )
        # extract polylines
        for e in msp.query("LWPOLYLINE"):
            vert = self.xy2latlong(e.vertices_in_wcs())
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
            vert = self.xy2latlong(e.flattening(0.1))
            layer_table[e.dxf.layer]["geometries"].append(
                {
                    "type": "Polygon",
                    "coordinates": [vert],
                }
            )
        # extract arcs
        for e in msp.query("ARC"):
            vert = self.xy2latlong(e.flattening(0.1))
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
        # handle blocks
        for block in doc.blocks:
            if block.name in self.name_blacklist:
                continue
            geometries = []
            # extract lines
            for e in block.query("LINE"):
                points = [e.dxf.start, e.dxf.end]
                vert = self.b_xy2latlong(points)
                geometries.append(
                    {
                        "type": "LineString",
                        "coordinates": vert,
                    }
                )
            # extract polylines
            for e in block.query("LWPOLYLINE"):
                vert = self.b_xy2latlong(e.vertices_in_wcs())
                if e.is_closed:
                    vert.append(vert[0])
                    geometries.append(
                        {
                            "type": "Polygon",
                            "coordinates": [vert],
                        }
                    )
                else:
                    geometries.append(
                        {
                            "type": "LineString",
                            "coordinates": vert,
                        }
                    )
            # extract circles
            for e in block.query("CIRCLE"):
                vert = self.b_xy2latlong(e.flattening(0.1))
                vert.append(vert[0])  # sometimes polygons don't close
                geometries.append(
                    {
                        "type": "Polygon",
                        "coordinates": [vert],
                    }
                )
            # extract arcs
            for e in block.query("ARC"):
                vert = self.b_xy2latlong(e.flattening(0.1))
                geometries.append(
                    {
                        "type": "LineString",
                        "coordinates": vert,
                    }
                )
            # create block as Layer
            if not geometries == []:
                Layer.objects.create(
                    drawing_id=self.id,
                    name=block.name,
                    geom={
                        "geometries": geometries,
                        "type": "GeometryCollection",
                    },
                    is_block=True,
                )
        # extract insertions
        for e in msp.query("INSERT"):
            if e.dxf.name in self.name_blacklist:
                continue
            try:
                layer = Layer.objects.get(drawing_id=self.id, name=e.dxf.layer)
                block = Layer.objects.get(drawing_id=self.id, name=e.dxf.name)
            except Layer.DoesNotExist:
                continue
            point = self.xy2latlong([e.dxf.insert])
            Insertion.objects.create(
                block=block,
                layer=layer,
                point=point,
                rotation=e.dxf.rotation,
                x_scale=e.dxf.xscale,
                y_scale=e.dxf.yscale,
            )

    def latlong2xy(self, vert):
        trans = []
        for v in vert:
            x = (
                -6371000
                * (radians(self.geom["coordinates"][0] - v[0]))
                * cos(radians(self.geom["coordinates"][1]))
            )
            y = -6371000 * (radians(self.geom["coordinates"][1] - v[1]))  # verify
            trans.append((x, y))
        return trans

    def get_file_to_download(self):
        doc = ezdxf.new()
        msp = doc.modelspace()
        drw_layers = self.related_layers.all()
        for drw_layer in drw_layers:
            if drw_layer.name != "0":
                doc_layer = doc.layers.add(drw_layer.name)
            else:
                doc_layer = doc.layers.get("0")
            color = ImageColor.getcolor(drw_layer.color_field, "RGB")
            doc_layer.rgb = color
            geometries = drw_layer.geom["geometries"]
            for geom in geometries:
                if geom["type"] == "Polygon":
                    vert = self.latlong2xy(geom["coordinates"][0])
                    msp.add_lwpolyline(
                        vert, dxfattribs={"layer": drw_layer.name}
                    ).close()
                else:
                    vert = self.latlong2xy(geom["coordinates"])
                    msp.add_lwpolyline(vert, dxfattribs={"layer": drw_layer.name})
        doc.saveas(filename=self.dxf.path, encoding="utf-8", fmt="asc")
        self.needs_refresh = False
        self.rotation = 0
        super(Drawing, self).save()


class Layer(models.Model):

    drawing = models.ForeignKey(
        Drawing,
        on_delete=models.CASCADE,
        related_name="related_layers",
        verbose_name=_("Drawing"),
    )
    name = models.CharField(
        _("Layer / block name"),
        max_length=50,
    )
    color_field = ColorField(default="#FFFFFF")
    geom = GeometryCollectionField(_("Entities"))
    is_block = models.BooleanField(
        _("Block definition"),
        default=False,
        editable=False,
    )

    class Meta:
        verbose_name = _("Layer")
        verbose_name_plural = _("Layers")

    def __str__(self):
        if self.is_block:
            return "block-" + self.name + "-" + str(self.id)
        return self.name + "-" + str(self.id)

    @property
    def popupContent(self):
        title_str = "<h6>%(layer)s: %(title)s</h6>" % {
            "layer": _("Layer"),
            "title": self.name,
        }
        return {"content": title_str, "color": self.color_field}

    def save(self, *args, **kwargs):
        super(Layer, self).save(*args, **kwargs)
        if not self.drawing.needs_refresh:
            self.drawing.needs_refresh = True
            super(Drawing, self.drawing).save()


class Insertion(models.Model):

    block = models.ForeignKey(
        Layer,
        on_delete=models.CASCADE,
        related_name="instances",
        verbose_name=_("Block"),
    )
    layer = models.ForeignKey(
        Layer,
        on_delete=models.CASCADE,
        related_name="insertions",
        verbose_name=_("Layer"),
    )
    point = PointField(_("Location"))
    rotation = models.FloatField(
        _("Rotation"),
        default=0,
    )
    x_scale = models.FloatField(
        _("X scale"),
        default=1,
    )
    y_scale = models.FloatField(
        _("Y scale"),
        default=1,
    )
    geom = GeometryCollectionField(_("Entities"), default={})
