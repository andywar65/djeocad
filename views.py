import json

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils.crypto import get_random_string
from django.utils.translation import gettext_lazy as _
from django.views.generic import DetailView, ListView

from .models import Drawing

User = get_user_model()


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


class AuthorDetailView(HxPageTemplateMixin, ListView):
    model = Drawing
    context_object_name = "drawings"
    template_name = "djeocad/htmx/author_detail.html"

    def setup(self, request, *args, **kwargs):
        super(AuthorDetailView, self).setup(request, *args, **kwargs)
        self.author = get_object_or_404(User, username=self.kwargs["username"])

    def get_queryset(self):
        self.qs = Drawing.objects.filter(user_id=self.author.uuid, private=False)
        if self.request.user.is_authenticated:
            qs2 = Drawing.objects.filter(user_id=self.request.user.uuid, private=True)
            self.qs = self.qs | qs2
        return self.qs.order_by(
            "id",
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["author"] = self.author
        context["mapbox_token"] = settings.MAPBOX_TOKEN
        if self.request.htmx:
            self.crypto = get_random_string(7)
            context["crypto"] = self.crypto
        return context

    def dispatch(self, request, *args, **kwargs):
        response = super(AuthorDetailView, self).dispatch(request, *args, **kwargs)
        if request.htmx:
            dict = {"getMarkerCollection": self.crypto}
            response["HX-Trigger-After-Swap"] = json.dumps(dict)
        return response


class DrawingDetailView(DetailView):
    model = Drawing
    context_object_name = "drawing"
    template_name = "djeocad/drawing_detail.html"

    def get_object(self, queryset=None):
        self.object = super(DrawingDetailView, self).get_object(queryset=None)
        user = get_object_or_404(User, username=self.kwargs["username"])
        if user != self.object.user:
            raise Http404(_("Drawing does not belong to User"))
        if self.object.private and self.object.user != self.request.user:
            raise PermissionDenied
        return self.object

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["author"] = self.object.user
        context["mapbox_token"] = settings.MAPBOX_TOKEN
        context["lines"] = self.object.drawing_layer.all()
        return context
