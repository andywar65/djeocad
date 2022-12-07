import json
from math import radians
from pathlib import Path

import ezdxf
from colorfield.fields import ColorField
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.validators import FileExtensionValidator
from django.db import IntegrityError, models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from djgeojson.fields import GeometryCollectionField, PointField
from filebrowser.base import FileObject
from filebrowser.fields import FileBrowseField
from PIL import ImageColor
from pyproj import Transformer
from pyproj.aoi import AreaOfInterest
from pyproj.database import query_utm_crs_info

from .utils import cad2hex, check_wide_image, latlong2xy, xy2latlong

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
        blank=True,
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
    geom = PointField(_("Location"), null=True)
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
    epsg = models.IntegerField(
        _("CRS code"),
        null=True,
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
            return {
                "content": title_str + intro_str,
                "layer": self.user.username,
            }
        image_str = '<img src="%(image)s">' % {"image": image}
        return {
            "content": title_str + image_str + intro_str,
            "layer": self.user.username,
        }

    def get_thumbnail_path(self):
        if not self.fb_image:
            return
        path = self.fb_image.version_generate("popup").path
        return settings.MEDIA_URL + path

    def save(self, *args, **kwargs):
        if not self.epsg:
            # let's try to find proper UTM
            utm_crs_list = query_utm_crs_info(
                datum_name="WGS 84",
                area_of_interest=AreaOfInterest(
                    west_lon_degree=self.geom["coordinates"][0],
                    south_lat_degree=self.geom["coordinates"][1],
                    east_lon_degree=self.geom["coordinates"][0],
                    north_lat_degree=self.geom["coordinates"][1],
                ),
            )
            self.epsg = utm_crs_list[0].code
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

    def extract_dxf(self):
        # following conditional for test to work
        if isinstance(self.geom, str):
            self.geom = json.loads(self.geom)
        # prepare transformers
        world2utm = Transformer.from_crs(4326, self.epsg, always_xy=True)
        utm2world = Transformer.from_crs(self.epsg, 4326)  # noqa
        utm_wcs = world2utm.transform(  # noqa
            self.geom["coordinates"][0], self.geom["coordinates"][1]
        )
        longp = self.geom["coordinates"][0]
        latp = self.geom["coordinates"][1]
        rot = radians(self.rotation)
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
            vert = xy2latlong(points, longp, latp, rot, 1, 1)
            layer_table[e.dxf.layer]["geometries"].append(
                {
                    "type": "LineString",
                    "coordinates": vert,
                }
            )
        # extract polylines
        for e in msp.query("LWPOLYLINE"):
            vert = xy2latlong(e.vertices_in_wcs(), longp, latp, rot, 1, 1)
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
            vert = xy2latlong(e.flattening(0.1), longp, latp, rot, 1, 1)
            layer_table[e.dxf.layer]["geometries"].append(
                {
                    "type": "Polygon",
                    "coordinates": [vert],
                }
            )
        # extract arcs
        for e in msp.query("ARC"):
            vert = xy2latlong(e.flattening(0.1), longp, latp, rot, 1, 1)
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
                vert = xy2latlong(points, 0, 0, 0, 1, 1)
                geometries.append(
                    {
                        "type": "LineString",
                        "coordinates": vert,
                    }
                )
            # extract polylines
            for e in block.query("LWPOLYLINE"):
                vert = xy2latlong(e.vertices_in_wcs(), 0, 0, 0, 1, 1)
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
                vert = xy2latlong(e.flattening(0.1), 0, 0, 0, 1, 1)
                vert.append(vert[0])  # sometimes polygons don't close
                geometries.append(
                    {
                        "type": "Polygon",
                        "coordinates": [vert],
                    }
                )
            # extract arcs
            for e in block.query("ARC"):
                vert = xy2latlong(e.flattening(0.1), 0, 0, 0, 1, 1)
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
            point = xy2latlong([e.dxf.insert], longp, latp, rot, 1, 1)[0]
            geometries_b = []
            for geom in block.geom["geometries"]:
                if geom["type"] == "Polygon":
                    vert = latlong2xy(geom["coordinates"][0], 0, 0)
                else:
                    vert = latlong2xy(geom["coordinates"], 0, 0)
                long_b = point[0]
                lat_b = point[1]
                rot_b = rot + radians(e.dxf.rotation)
                vert = xy2latlong(
                    vert, long_b, lat_b, rot_b, e.dxf.xscale, e.dxf.yscale
                )
                if geom["type"] == "Polygon":
                    geometries_b.append(
                        {
                            "type": "Polygon",
                            "coordinates": [vert],
                        }
                    )
                else:
                    geometries_b.append(
                        {
                            "type": "LineString",
                            "coordinates": vert,
                        }
                    )

            Insertion.objects.create(
                block=block,
                layer=layer,
                point={"type": "Point", "coordinates": point},
                rotation=e.dxf.rotation,
                x_scale=e.dxf.xscale,
                y_scale=e.dxf.yscale,
                geom={
                    "geometries": geometries_b,
                    "type": "GeometryCollection",
                },
            )

    def get_file_to_download(self):
        longp = self.geom["coordinates"][0]
        latp = self.geom["coordinates"][1]
        doc = ezdxf.new()
        msp = doc.modelspace()
        # create layers and add entities
        drw_layers = self.related_layers.filter(is_block=False)
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
                    vert = latlong2xy(geom["coordinates"][0], longp, latp)
                    msp.add_lwpolyline(
                        vert, dxfattribs={"layer": drw_layer.name}
                    ).close()
                else:
                    vert = latlong2xy(geom["coordinates"], longp, latp)
                    msp.add_lwpolyline(vert, dxfattribs={"layer": drw_layer.name})
        # create blocks and add entities
        drw_blocks = self.related_layers.filter(is_block=True)
        for drw_block in drw_blocks:
            block = doc.blocks.new(name=drw_block.name)
            geometries = drw_block.geom["geometries"]
            for geom in geometries:
                if geom["type"] == "Polygon":
                    vert = latlong2xy(geom["coordinates"][0], 0, 0)
                    block.add_lwpolyline(vert).close()
                else:
                    vert = latlong2xy(geom["coordinates"], 0, 0)
                    block.add_lwpolyline(vert)
        # add insertions
        for drw_layer in drw_layers:
            for insert in drw_layer.insertions.all():
                point = latlong2xy([insert.point["coordinates"]], longp, latp)
                msp.add_blockref(
                    insert.block.name,
                    point[0],
                    dxfattribs={
                        "xscale": insert.x_scale,
                        "yscale": insert.y_scale,
                        "rotation": insert.rotation + self.rotation,
                        "layer": insert.layer.name,
                    },
                )
                insert.rotation = insert.rotation + self.rotation
                insert.save()
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

    __original_name = None
    __original_geom = None

    class Meta:
        verbose_name = _("Layer")
        verbose_name_plural = _("Layers")
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(
                fields=["drawing", "name"], name="unique_layer_name"
            ),
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__original_name = self.name
        self.__original_geom = self.geom

    def __str__(self):
        if self.is_block:
            return "block-" + self.name + "-" + str(self.id)
        return self.name + "-" + str(self.id)

    def transform_to_block(self):
        # layer "0" can't be transformed in block
        if self.name == "0":
            return
        # already a block
        if self.is_block:
            return
        # get drawing's "0" layer
        zero = Layer.objects.get(drawing_id=self.drawing.id, name="0")
        # prepare and save block insertion
        insert = Insertion(
            layer=zero,
            block=self,
            point=self.drawing.geom,
            geom=self.geom,
        )
        insert.save()
        # get drawing origin
        long_d = self.drawing.geom["coordinates"][0]
        lat_d = self.drawing.geom["coordinates"][1]
        # prepare block geometries
        geometries_b = []
        for geom in self.geom["geometries"]:
            # from longlat to xy
            if geom["type"] == "Polygon":
                vert = latlong2xy(geom["coordinates"][0], long_d, lat_d)
            else:
                vert = latlong2xy(geom["coordinates"], long_d, lat_d)
            # back to longlat with coordinates (0,0)
            vert = xy2latlong(vert, 0, 0, 0, 1, 1)
            if geom["type"] == "Polygon":
                geometries_b.append(
                    {
                        "type": "Polygon",
                        "coordinates": [vert],
                    }
                )
            else:
                geometries_b.append(
                    {
                        "type": "LineString",
                        "coordinates": vert,
                    }
                )
        # prepare and save block
        self.geom = {
            "geometries": geometries_b,
            "type": "GeometryCollection",
        }
        self.color_field = "#FFFFFF"
        self.is_block = True
        super().save()

    @property
    def popupContent(self):
        if self.is_block:
            ltype = _("Block")
        else:
            ltype = _("Layer")
        title_str = "<h6>%(type)s: %(title)s, %(id)s: %(lid)d</h6>" % {
            "type": ltype,
            "title": self.name,
            "id": _("ID"),
            "lid": self.id,
        }
        return {
            "content": title_str,
            "color": self.color_field,
            "layer": self.name,
        }

    def save(self, *args, **kwargs):
        if self.__original_name == "0":
            self.name = "0"
        try:
            super(Layer, self).save(*args, **kwargs)
        except IntegrityError:
            self.name = self.__original_name
            super(Layer, self).save(*args, **kwargs)
        if not self.drawing.needs_refresh:
            self.drawing.needs_refresh = True
            super(Drawing, self.drawing).save()
        if self.is_block and self.__original_geom != self.geom:
            for insert in self.instances.all():
                geometries_b = []
                for geom in self.geom["geometries"]:
                    if geom["type"] == "Polygon":
                        vert = latlong2xy(geom["coordinates"][0], 0, 0)
                    else:
                        vert = latlong2xy(geom["coordinates"], 0, 0)
                    long_b = insert.point["coordinates"][0]
                    lat_b = insert.point["coordinates"][1]
                    rot_b = radians(insert.rotation)
                    vert = xy2latlong(
                        vert, long_b, lat_b, rot_b, insert.x_scale, insert.y_scale
                    )
                    if geom["type"] == "Polygon":
                        geometries_b.append(
                            {
                                "type": "Polygon",
                                "coordinates": [vert],
                            }
                        )
                    else:
                        geometries_b.append(
                            {
                                "type": "LineString",
                                "coordinates": vert,
                            }
                        )
                insert.geom = {
                    "geometries": geometries_b,
                    "type": "GeometryCollection",
                }
                insert.save()


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

    __original_point = None
    __original_rotation = None
    __original_x_scale = None
    __original_y_scale = None

    class Meta:
        ordering = ("-id",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__original_point = self.point
        self.__original_rotation = self.rotation
        self.__original_x_scale = self.x_scale
        self.__original_y_scale = self.y_scale

    @property
    def popupContent(self):
        title_str = """
            <ul><li>%(id)s: %(iid)d</li><li>%(layer)s: %(lname)s</li>
            <li>%(block)s: %(bname)s</li></ul>
            """ % {
            "id": _("ID"),
            "iid": self.id,
            "layer": _("Layer"),
            "lname": self.layer.name,
            "block": _("Block"),
            "bname": self.block.name,
        }
        return {
            "content": title_str,
            "color": self.layer.color_field,
            "layer": self.layer.name,
        }

    def explode_instance(self):
        self.layer.geom["geometries"] = (
            self.layer.geom["geometries"] + self.geom["geometries"]
        )
        self.layer.save()

    def save(self, *args, **kwargs):
        if (
            self.__original_point != self.point
            or self.__original_rotation != self.rotation
            or self.__original_x_scale != self.x_scale
            or self.__original_y_scale != self.y_scale
        ):
            if not self.layer.drawing.needs_refresh:
                self.layer.drawing.needs_refresh = True
                super(Drawing, self.layer.drawing).save()
            geometries_b = []
            for geom in self.block.geom["geometries"]:
                if geom["type"] == "Polygon":
                    vert = latlong2xy(geom["coordinates"][0], 0, 0)
                else:
                    vert = latlong2xy(geom["coordinates"], 0, 0)
                long_b = self.point["coordinates"][0]
                lat_b = self.point["coordinates"][1]
                rot_b = radians(self.rotation)
                vert = xy2latlong(
                    vert, long_b, lat_b, rot_b, self.x_scale, self.y_scale
                )
                if geom["type"] == "Polygon":
                    geometries_b.append(
                        {
                            "type": "Polygon",
                            "coordinates": [vert],
                        }
                    )
                else:
                    geometries_b.append(
                        {
                            "type": "LineString",
                            "coordinates": vert,
                        }
                    )
            self.geom = {
                "geometries": geometries_b,
                "type": "GeometryCollection",
            }
        super(Insertion, self).save(*args, **kwargs)
