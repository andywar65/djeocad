from django.urls import path
from django.utils.translation import gettext_lazy as _

from .views import AuthorDetailView, BaseListView, DrawingDetailView

app_name = "djeocad"
urlpatterns = [
    path("", BaseListView.as_view(), name="base_list"),
    path(_("author/<username>/"), AuthorDetailView.as_view(), name="author_detail"),
    path(
        _("author/<username>/drawing/<pk>/"),
        DrawingDetailView.as_view(),
        name="drawing_detail",
    ),
]
