from math import cos, degrees, fabs, radians, sin
from pathlib import Path

import ezdxf
from colorfield.fields import ColorField
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.validators import FileExtensionValidator
from django.db import models
from django.utils.translation import gettext_lazy as _
from djgeojson.fields import GeometryCollectionField, PointField
from filebrowser.base import FileObject
from filebrowser.fields import FileBrowseField

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
        help_text=_("Name of the building plan"),
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
            layers = self.drawing_layer.all()
            layers.delete()
            self.extract_dxf()

    def transform_vertices(self, vert):
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
        msp = doc.modelspace()  # noqa
        # prepare layer table
        layer_table = {}
        for layer in doc.layers:
            layer_table[layer.dxf.name] = {
                "color": cad2hex(layer.color),
                "linetype": layer.dxf.linetype,
                "geometries": [],
            }
        for e in msp.query("LINE"):
            points = [e.dxf.start, e.dxf.end]
            vert = self.transform_vertices(points)
            layer_table[e.dxf.layer]["geometries"].append(
                {
                    "type": "LineString",
                    "coordinates": vert,
                }
            )
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
        return


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
        return self.name
