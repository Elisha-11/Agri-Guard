from django.urls import path

from .views import DiagnosisHistoryView, DiagnosisSyncView, FeedbackView

urlpatterns = [
    path("diagnoses/", DiagnosisHistoryView.as_view(), name="diagnoses"),
    path("diagnoses/sync/", DiagnosisSyncView.as_view(), name="diagnoses-sync"),
    path("feedback/", FeedbackView.as_view(), name="feedback"),
]
