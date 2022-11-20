from django.urls import path
from django.utils.translation import gettext_lazy as _

from .views import (
    AuthorListView,
    BaseListView,
    DrawingCreateView,
    DrawingDeleteView,
    DrawingDetailView,
    DrawingUpdateView,
    LayerDeleteView,
    LayerUpdateView,
    drawing_download,
)

app_name = "djeocad"
urlpatterns = [
    path("", BaseListView.as_view(), name="base_list"),
    path(_("author/<username>/"), AuthorListView.as_view(), name="author_list"),
    path(
        _("author/<username>/drawing/<pk>/"),
        DrawingDetailView.as_view(),
        name="drawing_detail",
    ),
    path(
        _("author/<username>/drawing/add/"),
        DrawingCreateView.as_view(),
        name="drawing_create",
    ),
    path(
        _("author/<username>/drawing/<pk>/update/"),
        DrawingUpdateView.as_view(),
        name="drawing_update",
    ),
    path(
        _("author/<username>/drawing/<pk>/delete/"),
        DrawingDeleteView.as_view(),
        name="drawing_delete",
    ),
    path(
        _("author/<username>/layer/<pk>/update/"),
        LayerUpdateView.as_view(),
        name="layer_update",
    ),
    path(_("drawing/<pk>/download/"), drawing_download, name="drawing_download"),
    # Inlines
    path("layer/<pk>/delete/", LayerDeleteView.as_view(), name="layer_delete"),
]
