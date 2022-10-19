from django.contrib.auth import get_user_model
from django.core.validators import FileExtensionValidator
from django.db import models
from django.utils.translation import gettext_lazy as _
from djgeojson.fields import PointField
from filebrowser.fields import FileBrowseField

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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__original_dxf = self.dxf

    def __str__(self):
        return self.title
