from django.forms import ModelForm
from leaflet.forms.widgets import LeafletWidget

from .models import Drawing, Insertion, Layer


class DrawingCreateForm(ModelForm):
    class Meta:
        model = Drawing
        fields = ["title", "intro", "image", "dxf", "private"]
        widgets = {"geom": LeafletWidget()}


class DrawingUpdateForm(ModelForm):
    class Meta:
        model = Drawing
        fields = ["title", "intro", "image", "dxf", "geom", "rotation", "private"]
        widgets = {"geom": LeafletWidget()}

    class Media:
        js = ("djeocad/js/locate_user.js",)


class DrawingSimpleCreateForm(ModelForm):
    class Meta:
        model = Drawing
        fields = ["title", "intro", "dxf", "geom", "rotation"]
        widgets = {"geom": LeafletWidget()}


class LayerCreateForm(ModelForm):
    class Meta:
        model = Layer
        fields = ["name", "color_field", "geom"]
        widgets = {"geom": LeafletWidget()}


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
        widgets = {"point": LeafletWidget()}
