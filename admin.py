from django.contrib import admin
from leaflet.admin import LeafletGeoAdmin, LeafletGeoAdminMixin

from .models import Drawing, Layer


class LayerInline(LeafletGeoAdminMixin, admin.TabularInline):
    model = Layer
    fields = ("name", "color_field", "geom")
    extra = 0


class DrawingAdmin(LeafletGeoAdmin):
    list_display = ("title", "user")
    exclude = ("image",)
    inlines = [
        LayerInline,
    ]


admin.site.register(Drawing, DrawingAdmin)


class LayerAdmin(LeafletGeoAdmin):
    list_display = ("__str__", "drawing")


admin.site.register(Layer, LayerAdmin)
