from django.apps import AppConfig
from django.db.models.signals import post_migrate
from django.utils.translation import gettext as _


def create_djeocad_group(sender, **kwargs):
    from django.contrib.auth.models import Group, Permission
    from django.contrib.contenttypes.models import ContentType

    grp, created = Group.objects.get_or_create(name=_("GeoCAD Manager"))
    if created:
        types = ContentType.objects.filter(app_label="djeocad").values_list(
            "id", flat=True
        )
        permissions = Permission.objects.filter(content_type_id__in=types)
        grp.permissions.set(permissions)


class DjeocadConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "djeocad"

    def ready(self):
        #  import djeocad.signals  # noqa

        post_migrate.connect(create_djeocad_group, sender=self)
