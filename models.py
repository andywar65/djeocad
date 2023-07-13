import json
from math import atan2, cos, degrees, radians, sin
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
from ezdxf.addons import geo
from ezdxf.lldxf.const import InvalidGeoDataException
from ezdxf.math import Vec3
from filebrowser.base import FileObject
from filebrowser.fields import FileBrowseField
from PIL import ImageColor
from pyproj import Transformer
from pyproj.aoi import AreaOfInterest
from pyproj.database import query_utm_crs_info
from shapely.geometry import Point, shape
from shapely.geometry.polygon import Polygon

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
    designx = models.FloatField(
        _("Design point X..."),
        default=0,
    )
    designy = models.FloatField(
        _("...Y"),
        default=0,
    )
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
    __original_designx = None
    __original_designy = None
    __original_rotation = None
    name_blacklist = ["*Model_Space", "DynamicInputDot"]
    entity_types = [
        "POINT",
        "LINE",
        "LWPOLYLINE",
        "POLYLINE",
        "3DFACE",
        "CIRCLE",
        "ARC",
        "ELLIPSE",
        "SPLINE",
        "HATCH",
    ]

    class Meta:
        verbose_name = _("Drawing")
        verbose_name_plural = _("Drawings")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__original_dxf = self.dxf
        self.__original_geom = self.geom
        self.__original_designx = self.designx
        self.__original_designy = self.designy
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
                "layer": _("Author - ") + self.user.username,
            }
        image_str = '<img src="%(image)s">' % {"image": image}
        return {
            "content": title_str + image_str + intro_str,
            "layer": _("Author - ") + self.user.username,
        }

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
        # check if we have coordinate system
        if not self.epsg:
            # search for geodata in DXF
            doc = ezdxf.readfile(Path(settings.MEDIA_ROOT).joinpath(str(self.dxf)))
            msp = doc.modelspace()
            geodata = msp.get_geodata()
            if geodata:
                # check if valid XML and axis order
                try:
                    self.epsg, axis = geodata.get_crs()
                    if not axis:
                        return
                except InvalidGeoDataException:
                    return
                utm2world = Transformer.from_crs(self.epsg, 4326, always_xy=True)
                world_point = utm2world.transform(
                    geodata.dxf.reference_point[0], geodata.dxf.reference_point[1]
                )
                self.geom = {"type": "Point", "coordinates": world_point}
                self.designx = geodata.dxf.design_point[0]
                self.designy = geodata.dxf.design_point[1]
                self.rotation = degrees(
                    atan2(
                        geodata.dxf.north_direction[0], geodata.dxf.north_direction[1]
                    )
                )
                super(Drawing, self).save(*args, **kwargs)
            else:
                # can't find geodata in DXF, need manual insertion
                # check if user has inserted origin on map
                if self.geom:
                    # following conditional for test to work
                    if isinstance(self.geom, str):
                        self.geom = json.loads(self.geom)
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
                    super(Drawing, self).save(*args, **kwargs)
        # without geom we can't extract DXF
        if self.geom:
            if (
                self.__original_dxf != self.dxf
                or self.__original_geom != self.geom
                or self.__original_designx != self.designx
                or self.__original_designy != self.designy
                or self.__original_rotation != self.rotation
            ):
                self.related_layers.all().delete()
                self.extract_dxf()
                # flag drawing as refreshable
                if not self.needs_refresh:
                    self.needs_refresh = True
                    super(Drawing, self).save()

    def get_geo_proxy(self, entity, matrix, transformer):
        geo_proxy = geo.proxy(entity)
        if geo_proxy.geotype == "Polygon":
            if not shape(geo_proxy).is_valid:
                return False
        geo_proxy.wcs_to_crs(matrix)
        geo_proxy.apply(lambda v: Vec3(transformer.transform(v.x, v.y)))
        return geo_proxy

    def get_epsg_xml(self):
        xml = """<?xml version="1.0"
encoding="UTF-16" standalone="no" ?>
<Dictionary version="1.0" xmlns="http://www.osgeo.org/mapguide/coordinatesystem">
<Alias id="%(epsg)s" type="CoordinateSystem">
<ObjectId>EPSG=%(epsg)s</ObjectId>
<Namespace>EPSG Code</Namespace>
</Alias>
<Axis uom="METER">
<CoordinateSystemAxis>
<AxisOrder>1</AxisOrder>
<AxisName>Easting</AxisName>
<AxisAbbreviation>E</AxisAbbreviation>
<AxisDirection>east</AxisDirection>
</CoordinateSystemAxis>
<CoordinateSystemAxis>
<AxisOrder>2</AxisOrder>
<AxisName>Northing</AxisName>
<AxisAbbreviation>N</AxisAbbreviation>
<AxisDirection>north</AxisDirection>
</CoordinateSystemAxis>
</Axis>
</Dictionary>""" % {
            "epsg": self.epsg
        }
        return xml

    def prepare_transformers(self):
        world2utm = Transformer.from_crs(4326, self.epsg, always_xy=True)
        utm2world = Transformer.from_crs(self.epsg, 4326, always_xy=True)
        utm_wcs = world2utm.transform(
            self.geom["coordinates"][0], self.geom["coordinates"][1]
        )
        rot = radians(self.rotation)
        return world2utm, utm2world, utm_wcs, rot

    def fake_geodata(self, geodata, utm_wcs, rot):
        geodata.coordinate_system_definition = self.get_epsg_xml()
        geodata.dxf.design_point = (self.designx, self.designy, 0)
        geodata.dxf.reference_point = utm_wcs
        geodata.dxf.north_direction = (sin(rot), cos(rot))
        return geodata

    def extract_dxf(self):
        # limit the number of entities for non private drawings
        try:
            max_ent = settings.DJEOCAD_MAX_ENTITIES
        except AttributeError:
            max_ent = 20
        # following conditional for test to work
        if isinstance(self.geom, str):
            self.geom = json.loads(self.geom)
        # prepare transformers
        world2utm, utm2world, utm_wcs, rot = self.prepare_transformers()
        # get DXF
        doc = ezdxf.readfile(Path(settings.MEDIA_ROOT).joinpath(str(self.dxf)))
        msp = doc.modelspace()
        geodata = msp.get_geodata()
        if not geodata:
            # faking geodata
            geodata = msp.new_geodata()
            geodata = self.fake_geodata(geodata, utm_wcs, rot)
        # get transform matrix from true or fake geodata
        m, epsg = geodata.get_crs_transformation(no_checks=True)  # noqa
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
        for e_type in self.entity_types:
            i = 0
            # extract entities
            for e in msp.query(e_type):
                i += 1
                if not self.private and i >= max_ent:
                    break
                geo_proxy = self.get_geo_proxy(e, m, utm2world)
                if geo_proxy:
                    layer_table[e.dxf.layer]["geometries"].append(
                        geo_proxy.__geo_interface__
                    )
        # create Layers
        for name, layer in layer_table.items():
            if name == "0" or not layer["geometries"] == []:
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
            for e_type in self.entity_types:
                i = 0
                # extract entities
                for e in block.query(e_type):
                    i += 1
                    if not self.private and i >= max_ent:
                        break
                    geo_proxy = self.get_geo_proxy(e, m, utm2world)
                    if geo_proxy:
                        geometries.append(geo_proxy.__geo_interface__)
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
        for ins in msp.query("INSERT"):
            if ins.dxf.name in self.name_blacklist:
                continue
            try:
                layer = Layer.objects.get(drawing_id=self.id, name=ins.dxf.layer)
                block = Layer.objects.get(drawing_id=self.id, name=ins.dxf.name)
            except Layer.DoesNotExist:
                continue
            point = msp.add_point(ins.dxf.insert)
            geo_proxy = self.get_geo_proxy(point, m, utm2world)
            if geo_proxy:
                insertion_point = geo_proxy.__geo_interface__
            geometries = []
            # 'generator' object has no attribute 'query'
            for e in ins.virtual_entities():
                if e.dxftype() in self.entity_types:
                    # extract entity
                    geo_proxy = self.get_geo_proxy(e, m, utm2world)
                    if geo_proxy:
                        geometries.append(geo_proxy.__geo_interface__)
            # create Insertion
            Insertion.objects.create(
                block=block,
                layer=layer,
                point=insertion_point,
                rotation=ins.dxf.rotation,
                x_scale=ins.dxf.xscale,
                y_scale=ins.dxf.yscale,
                geom={
                    "geometries": geometries,
                    "type": "GeometryCollection",
                },
            )

    def get_file_to_download(self):
        # prepare transformers
        world2utm, utm2world, utm_wcs, rot = self.prepare_transformers()
        # start DXF
        doc = ezdxf.new()
        msp = doc.modelspace()
        # we fake geodata
        geodata = msp.new_geodata()
        geodata = self.fake_geodata(geodata, utm_wcs, rot)
        # get transform matrix from fake geodata
        m, epsg = geodata.get_crs_transformation(no_checks=True)  # noqa
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
                geo_proxy = geo.GeoProxy.parse(geom)
                geo_proxy.apply(lambda v: Vec3(world2utm.transform(v.x, v.y)))
                geo_proxy.crs_to_wcs(m)
                for entity in geo_proxy.to_dxf_entities(
                    dxfattribs={"layer": drw_layer.name}
                ):
                    msp.add_entity(entity)
        # create blocks and add entities
        drw_blocks = self.related_layers.filter(is_block=True)
        for drw_block in drw_blocks:
            block = doc.blocks.new(name=drw_block.name)
            geometries = drw_block.geom["geometries"]
            for geom in geometries:
                geo_proxy = geo.GeoProxy.parse(geom)
                geo_proxy.apply(lambda v: Vec3(world2utm.transform(v.x, v.y)))
                geo_proxy.crs_to_wcs(m)
                for entity in geo_proxy.to_dxf_entities(dxfattribs={"layer": "0"}):
                    block.add_entity(entity)
        # add insertions
        for drw_layer in drw_layers:
            for insert in drw_layer.insertions.all():
                geo_proxy = geo.GeoProxy.parse(insert.point)
                geo_proxy.apply(lambda v: Vec3(world2utm.transform(v.x, v.y)))
                geo_proxy.crs_to_wcs(m)
                for entity in geo_proxy.to_dxf_entities():
                    point = entity.dxf.location
                msp.add_blockref(
                    insert.block.name,
                    point,
                    dxfattribs={
                        "xscale": insert.x_scale,
                        "yscale": insert.y_scale,
                        "rotation": insert.rotation,
                        "layer": insert.layer.name,
                    },
                )
        # replace stored DXF
        doc.saveas(filename=self.dxf.path, encoding="utf-8", fmt="asc")
        # flag drawing as refreshed and save it
        self.needs_refresh = False
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
    linetype = models.BooleanField(
        _("Continuous linetype"),
        default=True,
    )
    geom = GeometryCollectionField(_("Entities"))
    is_block = models.BooleanField(
        _("Block definition"),
        default=False,
        editable=False,
    )

    __original_name = None
    __original_color_field = None
    __original_linetype = None
    __original_geom = None

    class Meta:
        verbose_name = _("Layer")
        verbose_name_plural = _("Layers")
        ordering = (
            "drawing",
            "name",
        )
        constraints = [
            models.UniqueConstraint(
                fields=["drawing", "name"], name="unique_layer_name"
            ),
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # access dict to avoid recursion error upon deleting parent (bug #31435)
        self.__original_name = self.__dict__.get("name")
        self.__original_color_field = self.__dict__.get("color_field")
        self.__original_linetype = self.__dict__.get("linetype")
        self.__original_geom = self.__dict__.get("geom")

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
        super(Insertion, insert).save()
        # transform layer into block and save it
        self.color_field = "#FFFFFF"
        self.is_block = True
        super(Layer, self).save()
        # flag drawing as refreshable
        if not self.drawing.needs_refresh:
            self.drawing.needs_refresh = True
            super(Drawing, self.drawing).save()

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
            "linetype": self.linetype,
            "layer": _("Layer - ") + self.name,
        }

    def save(self, *args, **kwargs):
        # can't change 0 layer name
        if self.__original_name == "0":
            self.name = "0"
        # check for layer unique name
        try:
            super(Layer, self).save(*args, **kwargs)
        except IntegrityError:
            self.name = self.__original_name
            super(Layer, self).save(*args, **kwargs)
        # flag drawing as refreshable if something changed
        if (
            self.__original_name != self.name
            or self.__original_color_field != self.color_field
            or self.__original_linetype != self.linetype
            or self.__original_geom != self.geom
        ):
            if not self.drawing.needs_refresh:
                self.drawing.needs_refresh = True
                super(Drawing, self.drawing).save()
        # if block geom changed, need to update instance geom
        if self.is_block and self.__original_geom != self.geom:
            # we will use a fake DXF to help us
            # prepare transformers
            world2utm, utm2world, utm_wcs, rot = self.drawing.prepare_transformers()
            # start fake DXF
            doc = ezdxf.new()
            msp = doc.modelspace()
            # we fake geodata
            geodata = msp.new_geodata()
            geodata = self.drawing.fake_geodata(geodata, utm_wcs, rot)
            # get transform matrix from fake geodata
            m, epsg = geodata.get_crs_transformation(no_checks=True)  # noqa
            # add block to fake DXF
            block = doc.blocks.new(name=self.name)
            geometries = self.geom["geometries"]
            for geom in geometries:
                geo_proxy = geo.GeoProxy.parse(geom)
                geo_proxy.apply(lambda v: Vec3(world2utm.transform(v.x, v.y)))
                geo_proxy.crs_to_wcs(m)
                for entity in geo_proxy.to_dxf_entities(dxfattribs={"layer": "0"}):
                    block.add_entity(entity)
            # handle instances
            for insert in self.instances.all():
                # add instance in fake DXF
                geo_proxy = geo.GeoProxy.parse(insert.point)
                geo_proxy.apply(lambda v: Vec3(world2utm.transform(v.x, v.y)))
                geo_proxy.crs_to_wcs(m)
                for entity in geo_proxy.to_dxf_entities():
                    point = entity.dxf.location
                instance = msp.add_blockref(
                    insert.block.name,
                    point,
                    dxfattribs={
                        "xscale": insert.x_scale,
                        "yscale": insert.y_scale,
                        "rotation": insert.rotation,
                        "layer": insert.layer.name,
                    },
                )
                # use fake instance to generate new geometries
                geometries = []
                # 'generator' object has no attribute 'query'
                for e in instance.virtual_entities():
                    if e.dxftype() in self.drawing.entity_types:
                        # extract entity
                        geo_proxy = self.drawing.get_geo_proxy(e, m, utm2world)
                        if geo_proxy:
                            geometries.append(geo_proxy.__geo_interface__)
                # update Insertion
                insert.geom = {
                    "geometries": geometries,
                    "type": "GeometryCollection",
                }
                super(Insertion, insert).save()


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
    geom = GeometryCollectionField(_("Entities"), default=dict)

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
            "linetype": self.layer.linetype,
            "layer": _("Layer - ") + self.layer.name,
        }

    def explode_instance(self):
        self.layer.geom["geometries"] = (
            self.layer.geom["geometries"] + self.geom["geometries"]
        )
        super(Layer, self.layer).save()
        # flag drawing as refreshable
        if not self.layer.drawing.needs_refresh:
            self.layer.drawing.needs_refresh = True
            super(Drawing, self.layer.drawing).save()

    def save(self, *args, **kwargs):
        # check if insertion has changed
        if (
            self.__original_point != self.point
            or self.__original_rotation != self.rotation
            or self.__original_x_scale != self.x_scale
            or self.__original_y_scale != self.y_scale
        ):
            # we will use a fake DXF to help us
            # prepare transformers
            drawing = self.layer.drawing
            world2utm, utm2world, utm_wcs, rot = drawing.prepare_transformers()
            # start fake DXF
            doc = ezdxf.new()
            msp = doc.modelspace()
            # we fake geodata
            geodata = msp.new_geodata()
            geodata = drawing.fake_geodata(geodata, utm_wcs, rot)
            # get transform matrix from fake geodata
            m, epsg = geodata.get_crs_transformation(no_checks=True)  # noqa
            # add block to fake DXF
            block = doc.blocks.new(name=self.block.name)
            geometries = self.block.geom["geometries"]
            for geom in geometries:
                geo_proxy = geo.GeoProxy.parse(geom)
                geo_proxy.apply(lambda v: Vec3(world2utm.transform(v.x, v.y)))
                geo_proxy.crs_to_wcs(m)
                for entity in geo_proxy.to_dxf_entities(dxfattribs={"layer": "0"}):
                    block.add_entity(entity)
            # add instance to fake DXF
            geo_proxy = geo.GeoProxy.parse(self.point)
            geo_proxy.apply(lambda v: Vec3(world2utm.transform(v.x, v.y)))
            geo_proxy.crs_to_wcs(m)
            for entity in geo_proxy.to_dxf_entities():
                point = entity.dxf.location
            instance = msp.add_blockref(
                block.name,
                point,
                dxfattribs={
                    "xscale": self.x_scale,
                    "yscale": self.y_scale,
                    "rotation": self.rotation,
                    "layer": "0",
                },
            )
            # use fake instance to generate new geometries
            geometries = []
            # 'generator' object has no attribute 'query'
            for e in instance.virtual_entities():
                if e.dxftype() in drawing.entity_types:
                    # extract entity
                    geo_proxy = drawing.get_geo_proxy(e, m, utm2world)
                    if geo_proxy:
                        geometries.append(geo_proxy.__geo_interface__)
            # update Insertion
            self.geom = {
                "geometries": geometries,
                "type": "GeometryCollection",
            }
            # flag drawing as refreshable
            if not drawing.needs_refresh:
                drawing.needs_refresh = True
                super(Drawing, drawing).save()
        super(Insertion, self).save(*args, **kwargs)


class Dxf2Csv(models.Model):

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
    intro = models.CharField(_("Notes"), null=True, max_length=200)

    class Meta:
        verbose_name = _("DXF 2 CSV")
        verbose_name_plural = _("DXF 2 CSVs")

    def __str__(self):
        return _("DXF 2 CSV - ") + str(self.id)

    def extract_data(self):
        # get DXF
        doc = ezdxf.readfile(Path(settings.MEDIA_ROOT).joinpath(str(self.dxf)))
        msp = doc.modelspace()
        # extract entities
        entity_types = [
            "LWPOLYLINE",
            "POLYLINE",
        ]
        data = []
        for e_type in entity_types:
            for p in msp.query(f"{e_type}[layer!='0']"):
                try:
                    poly = Polygon(p.vertices_in_wcs())
                except ValueError:
                    continue
                mtexts = msp.query(f"MTEXT[layer=='{p.dxf.layer}']")
                plan = ""
                id = ""
                for mtext in mtexts:
                    point = Point(mtext.dxf.insert)
                    if poly.contains(point):
                        text = mtext.text.split("/")
                        plan = text[0]
                        try:
                            id = text[1]
                        except IndexError:
                            pass
                data.append(
                    {
                        "plan": plan,
                        "id": id,
                        "layer": p.dxf.layer,
                        "surface": round(poly.area, 2),
                        "height": p.dxf.thickness,
                    }
                )
        return data
