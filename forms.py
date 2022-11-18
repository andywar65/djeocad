from django.forms import ModelForm
from leaflet.forms.widgets import LeafletWidget

from .models import Drawing


class DrawingCreateForm(ModelForm):
    class Meta:
        model = Drawing
        fields = ["title", "intro", "image", "dxf", "geom", "rotation", "private"]
        widgets = {"geom": LeafletWidget()}
