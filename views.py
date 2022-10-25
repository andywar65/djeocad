from django.conf import settings
from django.views.generic import ListView

from .models import Drawing


class HxPageTemplateMixin:
    """Switches template depending on request.htmx"""

    def get_template_names(self):
        if not self.request.htmx:
            return [self.template_name.replace("htmx/", "")]
        else:
            return [self.template_name]


class BaseListView(ListView):
    model = Drawing
    context_object_name = "drawings"
    template_name = "djeocad/base_list.html"

    def get_queryset(self):
        qs = Drawing.objects.filter(private=False)
        if self.request.user.is_authenticated:
            qs2 = Drawing.objects.filter(user_id=self.request.user.uuid, private=True)
            qs = qs | qs2
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        authors = Drawing.objects.values_list("user__username", flat=True)
        context["authors"] = list(dict.fromkeys(authors))
        context["mapbox_token"] = settings.MAPBOX_TOKEN
        return context
