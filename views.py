import json

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.crypto import get_random_string
from django.utils.translation import gettext_lazy as _
from django.views.generic import (
    CreateView,
    DetailView,
    ListView,
    RedirectView,
    TemplateView,
    UpdateView,
)

from .forms import (
    DrawingCreateForm,
    DrawingSimpleCreateForm,
    DrawingUpdateForm,
    InsertionCreateForm,
    LayerCreateForm,
)
from .models import Drawing, Insertion, Layer

User = get_user_model()


class HxPageTemplateMixin:
    """Switches template depending on request.htmx"""

    def get_template_names(self):
        if not self.request.htmx:
            return [self.template_name.replace("htmx/", "")]
        return [self.template_name]


class BaseListView(HxPageTemplateMixin, ListView):
    model = Drawing
    context_object_name = "drawings"
    template_name = "djeocad/htmx/base_list.html"

    def get_queryset(self):
        qs = Drawing.objects.filter(private=False)
        if self.request.user.is_authenticated:
            qs2 = Drawing.objects.filter(user_id=self.request.user.uuid, private=True)
            qs = qs | qs2
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        authors = Drawing.objects.values_list("user__username", flat=True)
        context["author_list"] = list(dict.fromkeys(authors))
        context["mapbox_token"] = settings.MAPBOX_TOKEN
        return context

    def dispatch(self, request, *args, **kwargs):
        response = super(BaseListView, self).dispatch(request, *args, **kwargs)
        if request.htmx:
            dict = {"refreshCollections": True}
            response["HX-Trigger-After-Swap"] = json.dumps(dict)
        return response


class AuthorListView(HxPageTemplateMixin, ListView):
    model = Drawing
    context_object_name = "drawings"
    template_name = "djeocad/htmx/author_list.html"

    def setup(self, request, *args, **kwargs):
        super(AuthorListView, self).setup(request, *args, **kwargs)
        self.author = get_object_or_404(User, username=self.kwargs["username"])

    def get_queryset(self):
        self.qs = Drawing.objects.filter(user_id=self.author.uuid, private=False)
        if self.request.user == self.author:
            qs2 = Drawing.objects.filter(user_id=self.author.uuid, private=True)
            self.qs = self.qs | qs2
        return self.qs.order_by(
            "id",
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["author"] = self.author
        context["author_list"] = [self.author.username]
        context["mapbox_token"] = settings.MAPBOX_TOKEN
        return context

    def dispatch(self, request, *args, **kwargs):
        response = super(AuthorListView, self).dispatch(request, *args, **kwargs)
        if request.htmx:
            dict = {"refreshCollections": True}
            response["HX-Trigger-After-Swap"] = json.dumps(dict)
        return response


class DrawingDetailView(HxPageTemplateMixin, DetailView):
    model = Drawing
    template_name = "djeocad/htmx/drawing_detail.html"

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
        context["mapbox_token"] = settings.MAPBOX_TOKEN
        context["lines"] = self.object.related_layers.filter(is_block=False)
        context["blocks"] = Insertion.objects.none()
        for layer in context["lines"]:
            context["blocks"] = context["blocks"] | layer.insertions.all()
        context["drawings"] = self.object
        context["author_list"] = [self.object.user.username]
        layer_list = context["lines"].values_list("name", flat=True)
        context["layer_list"] = list(dict.fromkeys(layer_list))
        return context

    def dispatch(self, request, *args, **kwargs):
        response = super(DrawingDetailView, self).dispatch(request, *args, **kwargs)
        if request.htmx:
            dict = {"refreshCollections": True}
            response["HX-Trigger-After-Swap"] = json.dumps(dict)
        return response


class DrawingCreateView(PermissionRequiredMixin, CreateView):
    permission_required = "djeocad.add_drawing"
    model = Drawing
    form_class = DrawingCreateForm
    template_name = "djeocad/includes/drawing_create.html"

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super(DrawingCreateView, self).form_valid(form)

    def get_success_url(self):
        if not self.object.epsg:
            messages.error(
                self.request,
                _(
                    """
                    No Geodata found. Please insert WCS Origin on map and Rotation
                    with respect to True North (counterclockwise is positive)
                    """
                ),
            )
            return reverse(
                "djeocad:drawing_update",
                kwargs={"username": self.request.user.username, "pk": self.object.id},
            )
        return reverse(
            "djeocad:drawing_detail",
            kwargs={"username": self.request.user.username, "pk": self.object.id},
        )


class DrawingSimpleCreateView(CreateView):
    model = Drawing
    form_class = DrawingSimpleCreateForm
    template_name = "djeocad/includes/drawing_simple_create.html"

    def form_valid(self, form):
        user = User.objects.get(username=_("geocad_visitors"))
        form.instance.user = user
        return super(DrawingSimpleCreateView, self).form_valid(form)

    def get_success_url(self):
        return reverse(
            "djeocad:drawing_detail",
            kwargs={"username": _("geocad_visitors"), "pk": self.object.id},
        )


class DrawingUpdateView(PermissionRequiredMixin, UpdateView):
    permission_required = "djeocad.change_drawing"
    model = Drawing
    form_class = DrawingUpdateForm
    template_name = "djeocad/includes/drawing_update.html"

    def get_object(self, queryset=None):
        self.object = super(DrawingUpdateView, self).get_object(queryset=None)
        user = get_object_or_404(User, username=self.kwargs["username"])
        if user != self.object.user or self.request.user != self.object.user:
            raise PermissionDenied
        return self.object

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["layers"] = self.object.related_layers.filter(is_block=False)
        context["blocks"] = self.object.related_layers.filter(is_block=True)
        return context

    def get_success_url(self):
        return reverse(
            "djeocad:drawing_detail",
            kwargs={"username": self.request.user.username, "pk": self.object.id},
        )


class DrawingDeleteView(PermissionRequiredMixin, RedirectView):
    permission_required = "djeocad.delete_drawing"

    def setup(self, request, *args, **kwargs):
        super(DrawingDeleteView, self).setup(request, *args, **kwargs)
        if not self.request.htmx:
            raise Http404(_("Request without HTMX headers"))
        get_object_or_404(User, username=self.kwargs["username"])
        drawing = get_object_or_404(Drawing, id=self.kwargs["pk"])
        if request.user != drawing.user:
            raise PermissionDenied
        drawing.delete()

    def get_redirect_url(self, *args, **kwargs):
        return reverse(
            "djeocad:author_list", kwargs={"username": self.kwargs["username"]}
        )

    def dispatch(self, request, *args, **kwargs):
        response = super(DrawingDeleteView, self).dispatch(request, *args, **kwargs)
        response["HX-Request"] = True
        return response


class LayerDetailView(HxPageTemplateMixin, DetailView):
    model = Layer
    template_name = "djeocad/htmx/layer_detail.html"

    def get_object(self, queryset=None):
        self.object = super(LayerDetailView, self).get_object(queryset=None)
        user = get_object_or_404(User, username=self.kwargs["username"])
        if user != self.object.drawing.user:
            raise Http404(_("Layer does not belong to User"))
        if (
            self.object.drawing.private
            and self.object.drawing.user != self.request.user
        ):
            raise PermissionDenied
        return self.object

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["mapbox_token"] = settings.MAPBOX_TOKEN
        context["drawings"] = self.object.drawing
        if self.request.htmx:
            self.m_crypto = get_random_string(7)
            context["m_crypto"] = self.m_crypto
            self.l_crypto = get_random_string(7)
            context["l_crypto"] = self.l_crypto
        else:
            context["lines"] = self.object
        return context

    def dispatch(self, request, *args, **kwargs):
        response = super(LayerDetailView, self).dispatch(request, *args, **kwargs)
        if request.htmx:
            dict = {
                "getMarkerCollection": self.m_crypto,
                "getLineCollection": self.l_crypto,
            }
            response["HX-Trigger-After-Swap"] = json.dumps(dict)
        return response


class LayerCreateView(PermissionRequiredMixin, CreateView):
    permission_required = "djeocad.add_layer"
    model = Layer
    form_class = LayerCreateForm
    template_name = "djeocad/includes/layer_create.html"

    def setup(self, request, *args, **kwargs):
        super(LayerCreateView, self).setup(request, *args, **kwargs)
        get_object_or_404(User, username=self.kwargs["username"])
        self.drawing = get_object_or_404(Drawing, id=self.kwargs["pk"])
        if request.user != self.drawing.user:
            raise PermissionDenied

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["drawing"] = self.drawing
        return context

    def post(self, request, *args, **kwargs):
        geometry = json.loads(request.POST["geom"])
        if geometry["type"] != "GeometryCollection":
            request.POST = request.POST.copy()
            request.POST["geom"] = json.dumps(
                {"type": "GeometryCollection", "geometries": [geometry]}
            )
        return super(LayerCreateView, self).post(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.drawing = self.drawing
        return super(LayerCreateView, self).form_valid(form)

    def get_success_url(self):
        return reverse(
            "djeocad:drawing_detail",
            kwargs={"username": self.drawing.user.username, "pk": self.drawing.id},
        )


class LayerUpdateView(PermissionRequiredMixin, UpdateView):
    permission_required = "djeocad.change_layer"
    model = Layer
    form_class = LayerCreateForm
    template_name = "djeocad/includes/layer_update.html"

    def get_object(self, queryset=None):
        self.object = super(LayerUpdateView, self).get_object(queryset=None)
        user = get_object_or_404(User, username=self.kwargs["username"])
        if (
            user != self.object.drawing.user
            or self.request.user != self.object.drawing.user
        ):
            raise PermissionDenied
        return self.object

    def post(self, request, *args, **kwargs):
        geometry = json.loads(request.POST["geom"])
        if geometry["type"] != "GeometryCollection":
            request.POST = request.POST.copy()
            request.POST["geom"] = json.dumps(
                {"type": "GeometryCollection", "geometries": [geometry]}
            )
        return super(LayerUpdateView, self).post(request, *args, **kwargs)

    def get_success_url(self):
        return reverse(
            "djeocad:drawing_detail",
            kwargs={
                "username": self.object.drawing.user.username,
                "pk": self.object.drawing.id,
            },
        )


class LayerToBlockView(PermissionRequiredMixin, RedirectView):
    permission_required = "djeocad.change_layer"

    def setup(self, request, *args, **kwargs):
        super(LayerToBlockView, self).setup(request, *args, **kwargs)
        get_object_or_404(User, username=self.kwargs["username"])
        self.layer = get_object_or_404(Layer, id=self.kwargs["pk"])
        if request.user != self.layer.drawing.user:
            raise PermissionDenied
        self.layer.transform_to_block()

    def get_redirect_url(self, *args, **kwargs):
        return reverse(
            "djeocad:drawing_detail",
            kwargs={
                "username": self.kwargs["username"],
                "pk": self.layer.drawing.id,
            },
        )


class LayerDeleteInlineView(PermissionRequiredMixin, TemplateView):
    permission_required = "djeocad.delete_layer"
    template_name = "djeocad/htmx/item_delete.html"

    def setup(self, request, *args, **kwargs):
        super(LayerDeleteInlineView, self).setup(request, *args, **kwargs)
        if not self.request.htmx:
            raise Http404(_("Request without HTMX headers"))
        layer = get_object_or_404(Layer, id=self.kwargs["pk"])
        if layer.name == "0":
            raise Http404(_("Can't delete layer '0'"))
        if request.user != layer.drawing.user:
            raise PermissionDenied
        name = layer.name
        layer.delete()
        messages.error(request, _('Layer "%s" deleted') % name)


class InsertionCreateView(PermissionRequiredMixin, CreateView):
    permission_required = "djeocad.add_insertion"
    model = Insertion
    form_class = InsertionCreateForm
    template_name = "djeocad/includes/insertion_create.html"

    def setup(self, request, *args, **kwargs):
        super(InsertionCreateView, self).setup(request, *args, **kwargs)
        get_object_or_404(User, username=self.kwargs["username"])
        self.block = get_object_or_404(Layer, id=self.kwargs["pk"])
        if not self.block.is_block:
            raise Http404(_("Layer is not a block"))
        if request.user != self.block.drawing.user:
            raise PermissionDenied

    def get_initial(self):
        initial = super(InsertionCreateView, self).get_initial()
        initial["layer"] = Layer.objects.get(
            drawing_id=self.block.drawing.id, name="0"
        ).id
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # 'blok' is not a typo
        context["blok"] = self.block
        return context

    def form_valid(self, form):
        form.instance.block = self.block
        return super(InsertionCreateView, self).form_valid(form)

    def get_success_url(self):
        return reverse(
            "djeocad:drawing_detail",
            kwargs={
                "username": self.kwargs["username"],
                "pk": self.block.drawing.id,
            },
        )


class InsertionUpdateView(PermissionRequiredMixin, UpdateView):
    permission_required = "djeocad.change_insertion"
    model = Insertion
    form_class = InsertionCreateForm
    template_name = "djeocad/includes/insertion_update.html"

    def get_object(self, queryset=None):
        self.object = super(InsertionUpdateView, self).get_object(queryset=None)
        user = get_object_or_404(User, username=self.kwargs["username"])
        if (
            user != self.object.block.drawing.user
            or self.request.user != self.object.block.drawing.user
        ):
            raise PermissionDenied
        return self.object

    def get_success_url(self):
        return reverse(
            "djeocad:drawing_detail",
            kwargs={
                "username": self.kwargs["username"],
                "pk": self.object.block.drawing.id,
            },
        )


class InsertionDeleteInlineView(PermissionRequiredMixin, TemplateView):
    permission_required = "djeocad.delete_insertion"
    template_name = "djeocad/htmx/item_delete.html"

    def setup(self, request, *args, **kwargs):
        super(InsertionDeleteInlineView, self).setup(request, *args, **kwargs)
        if not self.request.htmx:
            raise Http404(_("Request without HTMX headers"))
        insert = get_object_or_404(Insertion, id=self.kwargs["pk"])
        if request.user != insert.block.drawing.user:
            raise PermissionDenied
        id = insert.id
        insert.delete()
        messages.error(request, _('Insertion "%d" deleted') % id)


class InsertionExplodeInlineView(PermissionRequiredMixin, TemplateView):
    permission_required = "djeocad.delete_insertion"
    template_name = "djeocad/htmx/item_delete.html"

    def setup(self, request, *args, **kwargs):
        super(InsertionExplodeInlineView, self).setup(request, *args, **kwargs)
        if not self.request.htmx:
            raise Http404(_("Request without HTMX headers"))
        insert = get_object_or_404(Insertion, id=self.kwargs["pk"])
        if request.user != insert.block.drawing.user:
            raise PermissionDenied
        insert.explode_instance()
        id = insert.id
        insert.delete()
        messages.error(request, _('Insertion "%d" exploded') % id)


def drawing_download(request, pk):
    drawing = get_object_or_404(Drawing, id=pk)
    if drawing.private:
        if request.user != drawing.user:
            raise PermissionDenied
    if drawing.needs_refresh:
        drawing.get_file_to_download()
    response = HttpResponse(drawing.dxf, content_type="text/plain")
    response["Content-Disposition"] = "attachment; filename=%s.dxf" % drawing.title

    return response
