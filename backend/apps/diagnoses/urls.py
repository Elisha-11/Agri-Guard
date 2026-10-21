from django.urls import path

from .views import DiagnosisHistoryView, DiagnosisPhotoView, DiagnosisSyncView, FeedbackView

urlpatterns = [
    path("diagnoses/", DiagnosisHistoryView.as_view(), name="diagnoses"),
    path("diagnoses/sync/", DiagnosisSyncView.as_view(), name="diagnoses-sync"),
    path("diagnoses/<uuid:client_id>/photo/", DiagnosisPhotoView.as_view(), name="diagnosis-photo"),
    path("feedback/", FeedbackView.as_view(), name="feedback"),
]
