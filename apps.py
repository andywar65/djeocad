from django.apps import AppConfig
from django.db.models.signals import post_migrate
from django.utils.translation import gettext as _


def create_djeocad_group(sender, **kwargs):
    from django.contrib.auth import get_user_model
    from django.contrib.auth.hashers import make_password
    from django.contrib.auth.models import Group, Permission
    from django.contrib.contenttypes.models import ContentType

    User = get_user_model()

    grp, created = Group.objects.get_or_create(name=_("GeoCAD Manager"))
    if created:
        types = ContentType.objects.filter(app_label="djeocad").values_list(
            "id", flat=True
        )
        permissions = Permission.objects.filter(content_type_id__in=types)
        grp.permissions.set(permissions)

    try:
        user = User.objects.get(username=_("geocad_visitors"))
    except User.DoesNotExist:
        password = User.objects.make_random_password()
        user = User.objects.create_user(
            username=_("geocad_visitors"),
            password=make_password(password),
        )
        perm = Permission.objects.get(codename="change_profile")
        user.user_permissions.remove(perm)


class DjeocadConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "djeocad"

    def ready(self):
        #  import djeocad.signals  # noqa

        post_migrate.connect(create_djeocad_group, sender=self)
