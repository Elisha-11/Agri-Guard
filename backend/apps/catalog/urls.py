from django.urls import path

from .views import AdvisoryBundleView

urlpatterns = [
    path("advisory/bundle/", AdvisoryBundleView.as_view(), name="advisory-bundle"),
]
