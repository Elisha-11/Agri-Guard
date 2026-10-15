from django.urls import path

from .views import FarmListView

urlpatterns = [
    path("farms/", FarmListView.as_view(), name="farms"),
]
