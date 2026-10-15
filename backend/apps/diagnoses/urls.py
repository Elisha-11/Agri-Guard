from django.urls import path

from .views import DiagnosisSyncView

urlpatterns = [
    path("diagnoses/sync/", DiagnosisSyncView.as_view(), name="diagnoses-sync"),
]
