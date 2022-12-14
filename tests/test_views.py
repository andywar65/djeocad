from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from djeocad.models import Drawing

User = get_user_model()


@override_settings(
    USE_I18N=False, MEDIA_ROOT=Path(settings.MEDIA_ROOT).joinpath("temp")
)
class DjeocadViewTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        print("\nTest djeocad views")
        # Set up non-modified objects used by all test methods
        u = User.objects.create(
            username="andy.war65",
            password="P4s5W0r6",
            email="andy@war.com",
        )
        User.objects.create(
            username="not_author",
            password="P4s5W0r6",
            email="no@war.com",
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
        dp = Drawing(
            user_id=u.uuid,
            title="Bar",
            geom=point,
            image=SimpleUploadedFile("image.jpg", content, "image/jpg"),
            dxf=SimpleUploadedFile("test.dxf", content2, "file/dxf"),
            private=True,
        )
        dp.save()

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

    def test_list_and_detail_status_code_ok(self):
        u = User.objects.get(username="andy.war65")
        d = Drawing.objects.get(title="Foo")
        response = self.client.get(reverse("djeocad:base_list"))
        self.assertEqual(response.status_code, 200)
        print("\n-Tested base list view ok")
        response = self.client.get(
            reverse("djeocad:author_list", kwargs={"username": u.username})
        )
        self.assertEqual(response.status_code, 200)
        print("\n-Tested author list view ok")
        response = self.client.get(
            reverse(
                "djeocad:drawing_detail", kwargs={"username": u.username, "pk": d.id}
            )
        )
        self.assertEqual(response.status_code, 200)
        print("\n-Tested drawing detail view ok")

    def test_wrong_author_status_code_404(self):
        u = User.objects.get(username="not_author")
        d = Drawing.objects.get(title="Foo")
        response = self.client.get(
            reverse(
                "djeocad:drawing_detail", kwargs={"username": u.username, "pk": d.id}
            )
        )
        self.assertEqual(response.status_code, 404)
        print("\n-Tested drawing detail wrong author 404")

    def test_private_drawing_by_author_ok(self):
        self.client.login(username="andy.war65", password="P4s5W0r6")
        d = Drawing.objects.get(title="Bar")
        response = self.client.get(
            reverse(
                "djeocad:drawing_detail", kwargs={"username": "andy.war65", "pk": d.id}
            )
        )
        self.assertEqual(response.status_code, 200)
        print("\n-Tested private drawing by author ok")

    def test_private_drawing_by_not_author_fail(self):
        self.client.login(username="not_author", password="P4s5W0r6")
        d = Drawing.objects.get(title="Bar")
        response = self.client.get(
            reverse(
                "djeocad:drawing_detail", kwargs={"username": "andy.war65", "pk": d.id}
            )
        )
        self.assertEqual(response.status_code, 403)
        print("\n-Tested private drawing by not author fail")

    def test_list_detail_template_used(self):
        u = User.objects.get(username="andy.war65")
        d = Drawing.objects.get(title="Foo")
        response = self.client.get(reverse("djeocad:base_list"))
        self.assertTemplateUsed(response, "djeocad/base_list.html")
        print("\n-Test base list template")
        response = self.client.get(
            reverse("djeocad:author_list", kwargs={"username": u.username})
        )
        self.assertTemplateUsed(response, "djeocad/author_list.html")
        print("\n-Tested author list template")
        response = self.client.get(
            reverse(
                "djeocad:drawing_detail", kwargs={"username": u.username, "pk": d.id}
            )
        )
        self.assertTemplateUsed(response, "djeocad/drawing_detail.html")
        print("\n-Tested drawing detail template")
