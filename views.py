import csv
import json

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import permission_required
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    RedirectView,
    TemplateView,
    UpdateView,
)
from filer.models import Image

from .forms import (
    DrawingCreateForm,
    DrawingGeoDataForm,
    DrawingSimpleCreateForm,
    DrawingUpdateForm,
    Dxf2CsvCreateForm,
    InsertionCreateForm,
    LayerCreateForm,
)
from .models import Drawing, Dxf2Csv, Insertion, Layer

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
        qs = Drawing.objects.filter(private=False).prefetch_related("user")
        if self.request.user.is_authenticated:
            qs2 = Drawing.objects.filter(user_id=self.request.user.uuid, private=True)
            qs = qs | qs2
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        authors = Drawing.objects.values_list("user__username", flat=True)
        context["authors"] = list(dict.fromkeys(authors))
        context["author_list"] = [_("Author - ") + s for s in context["authors"]]
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
        self.qs = Drawing.objects.filter(
            user_id=self.author.uuid, private=False
        ).select_related("user")
        if self.request.user == self.author:
            qs2 = Drawing.objects.filter(user_id=self.author.uuid, private=True)
            self.qs = self.qs | qs2
        return self.qs.order_by(
            "id",
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["author"] = self.author
        context["author_list"] = [_("Author - ") + self.author.username]
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
        context["blocks"] = self.object.related_layers.filter(is_block=True)
        id_list = context["lines"].values_list("id", flat=True)
        context["insertions"] = Insertion.objects.filter(layer_id__in=id_list)
        context["drawings"] = self.object
        context["author_list"] = [_("Author - ") + self.object.user.username]
        name_list = context["lines"].values_list("name", flat=True)
        context["layer_list"] = list(dict.fromkeys(name_list))
        context["layer_list"] = [_("Layer - ") + s for s in context["layer_list"]]
        return context

    def dispatch(self, request, *args, **kwargs):
        response = super(DrawingDetailView, self).dispatch(request, *args, **kwargs)
        if request.htmx:
            dict = {"refreshCollections": True}
            response["HX-Trigger-After-Swap"] = json.dumps(dict)
        return response


class DrawingCreateView(PermissionRequiredMixin, HxPageTemplateMixin, CreateView):
    permission_required = "djeocad.add_drawing"
    model = Drawing
    form_class = DrawingCreateForm
    template_name = "djeocad/htmx/drawing_create.html"

    def form_valid(self, form):
        form.instance.user = self.request.user
        if form.cleaned_data["image"]:
            img = Image.objects.create(
                owner=self.request.user,
                original_filename=form.cleaned_data["title"],
                file=form.cleaned_data["image"],
            )
            form.instance.fb_image = img
        form.instance.image = None
        return super(DrawingCreateView, self).form_valid(form)

    def get_success_url(self):
        if not self.object.epsg:
            return reverse(
                "djeocad:drawing_geodata",
                kwargs={"username": self.request.user.username, "pk": self.object.id},
            )
        return reverse(
            "djeocad:drawing_detail",
            kwargs={"username": self.request.user.username, "pk": self.object.id},
        )


class DrawingGeoDataView(PermissionRequiredMixin, UpdateView):
    permission_required = "djeocad.change_drawing"
    model = Drawing
    form_class = DrawingGeoDataForm
    template_name = "djeocad/includes/drawing_geodata.html"

    def get_object(self, queryset=None):
        self.object = super(DrawingGeoDataView, self).get_object(queryset=None)
        user = get_object_or_404(User, username=self.kwargs["username"])
        if user != self.object.user or self.request.user != self.object.user:
            raise PermissionDenied
        return self.object

    def get_success_url(self):
        return reverse(
            "djeocad:drawing_detail",
            kwargs={"username": self.request.user.username, "pk": self.object.id},
        )


class DrawingSimpleCreateView(HxPageTemplateMixin, CreateView):
    model = Drawing
    form_class = DrawingSimpleCreateForm
    template_name = "djeocad/htmx/drawing_simple_create.html"

    def form_valid(self, form):
        user = User.objects.get(username=_("geocad_visitors"))
        form.instance.user = user
        return super(DrawingSimpleCreateView, self).form_valid(form)

    def get_success_url(self):
        if not self.object.epsg:
            return reverse(
                "djeocad:drawing_simple_geodata",
                kwargs={"pk": self.object.id},
            )
        return reverse(
            "djeocad:drawing_detail",
            kwargs={"username": _("geocad_visitors"), "pk": self.object.id},
        )


class DrawingSimpleGeoDataView(UpdateView):
    model = Drawing
    form_class = DrawingGeoDataForm
    template_name = "djeocad/includes/drawing_geodata.html"

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


class DrawingDeleteView(PermissionRequiredMixin, DeleteView):
    model = Drawing
    permission_required = "djeocad.delete_drawing"

    def setup(self, request, *args, **kwargs):
        super(DrawingDeleteView, self).setup(request, *args, **kwargs)
        if not request.htmx and not request.POST:
            raise Http404(_("Request without HTMX headers"))
        get_object_or_404(User, username=self.kwargs["username"])
        drawing = get_object_or_404(Drawing, id=self.kwargs["pk"])
        if request.user != drawing.user:
            raise PermissionDenied

    def get_success_url(self, *args, **kwargs):
        return reverse(
            "djeocad:author_list", kwargs={"username": self.kwargs["username"]}
        )


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


class LayerDeleteView(PermissionRequiredMixin, DeleteView):
    model = Layer
    permission_required = "djeocad.delete_layer"

    def get_object(self, queryset=None):
        obj = super(LayerDeleteView, self).get_object(queryset=None)
        if obj.name == "0":
            raise PermissionDenied
        if not self.request.htmx and not self.request.POST:
            raise Http404(_("Request without HTMX headers"))
        get_object_or_404(User, username=self.kwargs["username"])
        self.drawing = obj.drawing
        if self.request.user != self.drawing.user:
            raise PermissionDenied
        return obj

    def get_success_url(self, *args, **kwargs):
        return reverse(
            "djeocad:drawing_detail",
            kwargs={"username": self.kwargs["username"], "pk": self.drawing.id},
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


class InsertionDeleteView(PermissionRequiredMixin, DeleteView):
    model = Insertion
    permission_required = "djeocad.delete_insertion"

    def get_object(self, queryset=None):
        obj = super(InsertionDeleteView, self).get_object(queryset=None)
        if not self.request.htmx and not self.request.POST:
            raise Http404(_("Request without HTMX headers"))
        get_object_or_404(User, username=self.kwargs["username"])
        self.drawing = obj.layer.drawing
        if self.request.user != self.drawing.user:
            raise PermissionDenied
        return obj

    def get_success_url(self, *args, **kwargs):
        return reverse(
            "djeocad:drawing_detail",
            kwargs={"username": self.kwargs["username"], "pk": self.drawing.id},
        )


class InsertionExplodeView(InsertionDeleteView):
    def form_valid(self, form):
        success_url = self.get_success_url()
        self.object.explode_instance()
        self.object.delete()
        return HttpResponseRedirect(success_url)


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


class Dxf2CsvCreateView(PermissionRequiredMixin, HxPageTemplateMixin, CreateView):
    permission_required = "djeocad.add_dxf2csv"
    model = Dxf2Csv
    form_class = Dxf2CsvCreateForm
    template_name = "djeocad/htmx/dxf2csv_create.html"

    def get_success_url(self, *args, **kwargs):
        return reverse("djeocad:dxf2csv_detail", kwargs={"pk": self.object.id})


class Dxf2CsvDetailView(PermissionRequiredMixin, HxPageTemplateMixin, DetailView):
    permission_required = "djeocad.view_dxf2csv"
    model = Dxf2Csv
    template_name = "djeocad/htmx/dxf2csv_download.html"


def csv_writer(writer, dxf):
    writer.writerow([dxf.intro])
    writer.writerow(
        [
            _("Floor"),
            _("ID"),
            _("Function"),
            _("Intervention"),
            _("Surface"),
            _("Height"),
            _("Volume"),
        ]
    )
    data = dxf.extract_data()
    for d in data:
        writer.writerow(
            [
                d["plan"],
                d["id"],
                d["layer"],
                d["interv"],
                d["surface"],
                d["height"],
                d["volume"],
            ]
        )
    return writer


@permission_required("djeocad.view_dxf2csv")
def csv_download(request, pk):
    dxf = get_object_or_404(Dxf2Csv, id=pk)
    # Create the HttpResponse object with the appropriate CSV header.
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{dxf.__str__()}.csv"'

    writer = csv.writer(response)
    writer = csv_writer(writer, dxf)

    return response
