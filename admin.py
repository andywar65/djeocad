from django.contrib import admin
from leaflet.admin import LeafletGeoAdmin, LeafletGeoAdminMixin

from .models import Drawing, Dxf2Csv, Insertion, Layer


class LayerInline(LeafletGeoAdminMixin, admin.TabularInline):
    model = Layer
    fields = ("name", "color_field", "geom")
    extra = 0


class InsertionInline(LeafletGeoAdminMixin, admin.TabularInline):
    model = Insertion
    fk_name = "block"
    fields = ("layer", "point", "rotation", "x_scale", "y_scale")
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
    inlines = [
        InsertionInline,
    ]


admin.site.register(Layer, LayerAdmin)


@admin.register(Dxf2Csv)
class Dxf2CsvAdmin(admin.ModelAdmin):
    list_display = (
        "__str__",
        "intro",
    )
