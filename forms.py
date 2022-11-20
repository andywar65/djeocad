from django.forms import ModelForm
from leaflet.forms.widgets import LeafletWidget

from .models import Drawing, Layer


class DrawingCreateForm(ModelForm):
    class Meta:
        model = Drawing
        fields = ["title", "intro", "image", "dxf", "geom", "rotation", "private"]
        widgets = {"geom": LeafletWidget()}


class LayerCreateForm(ModelForm):
    class Meta:
        model = Layer
        fields = ["name", "color_field", "geom"]
        widgets = {"geom": LeafletWidget()}
