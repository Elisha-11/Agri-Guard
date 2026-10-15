from django.contrib import admin

from .models import Diagnosis, Feedback


class FeedbackInline(admin.TabularInline):
    model = Feedback
    fk_name = "diagnosis"
    extra = 0
    raw_id_fields = ["given_by"]


@admin.register(Diagnosis)
class DiagnosisAdmin(admin.ModelAdmin):
    """Diagnoses are append-only (docs/offline-sync.md), so the prediction fields are read-only here."""

    list_display = ["captured_at", "disease", "confidence", "status", "severity", "farmer", "model_version"]
    list_filter = ["status", "severity", "crop", "model_version", "disease"]
    search_fields = ["client_id", "farmer__phone", "disease__class_id"]
    date_hierarchy = "captured_at"
    raw_id_fields = ["farmer", "farm"]
    readonly_fields = [
        "id",
        "client_id",
        "received_at",
        "crop",
        "disease",
        "class_index",
        "confidence",
        "status",
        "severity",
        "top_k",
        "model_version",
        "inference_ms",
        "captured_at",
        "app_version",
    ]
    inlines = [FeedbackInline]


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ["created_at", "diagnosis", "was_correct", "corrected_disease", "given_by_role"]
    list_filter = ["was_correct", "given_by_role"]
    raw_id_fields = ["diagnosis", "given_by"]
