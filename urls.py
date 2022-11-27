from django.urls import path
from django.utils.translation import gettext_lazy as _

from .views import (
    AuthorListView,
    BaseListView,
    DrawingCreateView,
    DrawingDeleteView,
    DrawingDetailView,
    DrawingUpdateView,
    InsertionCreateView,
    InsertionDeleteInlineView,
    InsertionExplodeInlineView,
    InsertionUpdateView,
    LayerCreateView,
    LayerDeleteInlineView,
    LayerDetailView,
    LayerUpdateView,
    drawing_download,
)

app_name = "djeocad"
urlpatterns = [
    path("", BaseListView.as_view(), name="base_list"),
    path("<username>/", AuthorListView.as_view(), name="author_list"),
    path(
        _("<username>/drawing/<pk>/"),
        DrawingDetailView.as_view(),
        name="drawing_detail",
    ),
    path(
        _("<username>/drawing/add/"),
        DrawingCreateView.as_view(),
        name="drawing_create",
    ),
    path(
        _("<username>/drawing/<pk>/update/"),
        DrawingUpdateView.as_view(),
        name="drawing_update",
    ),
    path(
        _("<username>/drawing/<pk>/delete/"),
        DrawingDeleteView.as_view(),
        name="drawing_delete",
    ),
    path(
        _("<username>/drawing/<pk>/layer/add/"),
        LayerCreateView.as_view(),
        name="layer_create",
    ),
    path(
        _("<username>/layer/<pk>/"),
        LayerDetailView.as_view(),
        name="layer_detail",
    ),
    path(
        _("<username>/layer/<pk>/update/"),
        LayerUpdateView.as_view(),
        name="layer_update",
    ),
    path(
        _("<username>/block/<pk>/instance/add/"),
        InsertionCreateView.as_view(),
        name="insert_create",
    ),
    path(
        _("<username>/block-instance/<pk>/update/"),
        InsertionUpdateView.as_view(),
        name="insert_update",
    ),
    path(_("drawing/<pk>/download/"), drawing_download, name="drawing_download"),
    # Inlines
    path(
        "layer/<pk>/delete/",
        LayerDeleteInlineView.as_view(),
        name="layer_delete_inline",
    ),
    path(
        "insertion/<pk>/explode/",
        InsertionExplodeInlineView.as_view(),
        name="insert_explode_inline",
    ),
    path(
        "insertion/<pk>/delete/",
        InsertionDeleteInlineView.as_view(),
        name="insert_delete_inline",
    ),
]
