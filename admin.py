from django.contrib import admin  # noqa
from leaflet.admin import LeafletGeoAdmin

from .models import Drawing


class DrawingAdmin(LeafletGeoAdmin):
    list_display = ("title", "user")
    exclude = ("image",)


admin.site.register(Drawing, DrawingAdmin)
