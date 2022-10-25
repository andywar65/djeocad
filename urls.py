from django.urls import path

from .views import BaseListView

app_name = "djeocad"
urlpatterns = [
    path("", BaseListView.as_view(), name="base_list"),
]
