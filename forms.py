from django.forms import ModelForm
from leaflet.forms.widgets import LeafletWidget

from .models import Drawing, Dxf2Csv, Insertion, Layer


class DrawingCreateForm(ModelForm):
    class Meta:
        model = Drawing
        fields = ["title", "intro", "dxf", "image", "private"]


class DrawingGeoDataForm(ModelForm):
    class Meta:
        model = Drawing
        fields = ["geom", "designx", "designy", "rotation"]
        widgets = {
            "geom": LeafletWidget(
                attrs={
                    "geom_type": "Point",
                }
            )
        }

    class Media:
        js = ("djeocad/js/locate_user.js",)


class DrawingUpdateForm(ModelForm):
    class Meta:
        model = Drawing
        fields = [
            "title",
            "intro",
            "dxf",
            "image",
            "geom",
            "designx",
            "designy",
            "rotation",
            "private",
        ]
        widgets = {
            "geom": LeafletWidget(
                attrs={
                    "geom_type": "Point",
                }
            )
        }


class DrawingSimpleCreateForm(ModelForm):
    class Meta:
        model = Drawing
        fields = ["title", "intro", "dxf"]


class LayerCreateForm(ModelForm):
    class Meta:
        model = Layer
        fields = ["name", "color_field", "linetype", "geom"]
        widgets = {
            "geom": LeafletWidget(
                attrs={
                    "geom_type": "GeometryCollection",
                }
            )
        }

    class Media:
        js = ("djeocad/js/locate_drawing.js",)


class InsertionCreateForm(ModelForm):
    def __init__(self, **kwargs):
        super(InsertionCreateForm, self).__init__(**kwargs)
        # filter layer queryset
        layer = Layer.objects.get(id=self.initial["layer"])
        self.fields["layer"].queryset = Layer.objects.filter(
            drawing_id=layer.drawing.id, is_block=False
        )

    class Meta:
        model = Insertion
        fields = [
            "layer",
            "point",
            "rotation",
            "x_scale",
            "y_scale",
        ]
        widgets = {
            "point": LeafletWidget(
                attrs={
                    "geom_type": "Point",
                }
            )
        }

    class Media:
        js = ("djeocad/js/locate_drawing.js",)


class Dxf2CsvCreateForm(ModelForm):
    class Meta:
        model = Dxf2Csv
        fields = ["dxf", "intro"]
