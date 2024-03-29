from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from djeocad.models import Drawing, Layer

User = get_user_model()


@override_settings(
    USE_I18N=False, MEDIA_ROOT=Path(settings.MEDIA_ROOT).joinpath("temp")
)
class DjeocadModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        print("\nTest djeocad models")
        # Set up non-modified objects used by all test methods
        u = User.objects.create(
            username="andy.war65",
            password="P4s5W0r6",
            email="andy@war.com",
        )
        point = '{"type": "Point","coordinates": [12.493652,41.866288]}'
        d = Drawing(
            user_id=u.uuid,
            title="Foo",
            geom=point,
        )
        img_path = Path(settings.STATIC_ROOT).joinpath("djeocad/tests/image.jpg")
        with open(img_path, "rb") as file:
            content = file.read()
        d.image = SimpleUploadedFile("image.jpg", content, "image/jpg")
        dxf_path = Path(settings.STATIC_ROOT).joinpath("djeocad/tests/test.dxf")
        with open(dxf_path, "rb") as file:
            content2 = file.read()
        d.dxf = SimpleUploadedFile("test.dxf", content2, "file/dxf")
        d.save()
        geometry = """{
                        "type": "GeometryCollection",
                        "geometries": [
                            {
                                "type": "LineString",
                                "coordinates": [
                                    [
                                        12.476042247774025,
                                        41.9061408746708
                                    ],
                                    [
                                        12.476845338429273,
                                        41.90596205712406
                                    ]
                                ]
                            }
                        ]
                    }"""
        Layer.objects.create(drawing_id=d.id, name="Layer", geom=geometry)

    def tearDown(self):
        """Checks existing files, then removes them"""
        path = Path(settings.MEDIA_ROOT).joinpath("uploads/images/drawing/")
        list = [e for e in path.iterdir() if e.is_file()]
        for file in list:
            Path(file).unlink()
        path = Path(settings.MEDIA_ROOT).joinpath("_versions/images/drawing/")
        list = [e for e in path.iterdir() if e.is_file()]
        for file in list:
            Path(file).unlink()
        path = Path(settings.MEDIA_ROOT).joinpath("uploads/djeocad/dxf/")
        list = [e for e in path.iterdir() if e.is_file()]
        for file in list:
            Path(file).unlink()

    def test_model__str__(self):
        d = Drawing.objects.get(title="Foo")
        self.assertEquals(d.__str__(), "Foo")
        print("\n-Tested drawing __str__")
        y = Layer.objects.get(name="Layer")
        self.assertEquals(y.__str__(), "Layer-" + str(y.id))
        print("\n-Tested layer __str__")

    def test_get_thumbnail_path(self):
        d = Drawing.objects.get(title="Foo")
        self.assertEquals(
            d.get_thumbnail_path(), "/media/_versions/images/drawing/image_popup.jpg"
        )
        print("\n-Tested drawing get_thumbnail_path")

    def test_popupContent(self):
        d = Drawing.objects.get(title="Foo")
        self.assertEquals(
            d.popupContent,
            {
                "content": '<h5><a href="/it/geocad/andy.war65/disegno/1/">'
                + 'Foo</a></h5><img src="/media/"><small>None</small>',
                "layer": "Autore - andy.war65",
            },
        )
        print("\n-Tested drawing popupContent")
        y = Layer.objects.get(name="Layer")
        self.assertEquals(
            y.popupContent,
            {
                "color": "#FFFFFF",
                "content": "<h6>Livello: Layer, ID: 5</h6>",
                "layer": "Livello - Layer",
                "linetype": True,
            },
        )
        print("\n-Tested layer popupContent")
