#  from pathlib import Path

#  from django.conf import settings
from django.contrib.auth import get_user_model

#  from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from djeocad.models import Drawing, Layer

User = get_user_model()


@override_settings(USE_I18N=False)
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
        d = Drawing.objects.create(
            user_id=u.uuid,
            title="Foo",
            geom=point,
            dxf="dummy/file.dxf",
        )
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

    def test_model__str__(self):
        d = Drawing.objects.get(title="Foo")
        self.assertEquals(d.__str__(), "Foo")
        print("\n-Tested drawing __str__")
        y = Layer.objects.get(name="Layer")
        self.assertEquals(y.__str__(), "Layer-" + str(y.id))
        print("\n-Tested layer __str__")
