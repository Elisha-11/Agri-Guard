from django.urls import path

from .views import DiagnosisSyncView, FeedbackView

urlpatterns = [
    path("diagnoses/sync/", DiagnosisSyncView.as_view(), name="diagnoses-sync"),
    path("feedback/", FeedbackView.as_view(), name="feedback"),
]
