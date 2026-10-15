from django.urls import path

from .views import LatestModelView

urlpatterns = [
    path("model/latest/", LatestModelView.as_view(), name="model-latest"),
]
