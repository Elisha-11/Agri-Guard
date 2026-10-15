"""Diagnoses made on phones and synced later, plus feedback on whether they were right.

Both are append-only (docs/offline-sync.md, "Conflict policy"): a prediction is never edited after the fact,
and a correction is a new Feedback row. Both carry a client-generated `client_id`, the idempotency key for
sync.
"""

import uuid
from datetime import UTC, datetime, timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxLengthValidator
from django.db import models
from django.db.models import Q

from apps.core.choices import Crop, PredictionStatus, Role, Severity
from apps.core.models import GeoPointMixin
from apps.core.validators import PROBABILITY_VALIDATORS

# offline-sync.md, "Clock skew": device clocks before this date are treated as wrong.
EARLIEST_PLAUSIBLE_CAPTURE = datetime(2026, 1, 1, tzinfo=UTC)
MAX_CAPTURE_AFTER_RECEIPT = timedelta(days=30)


def validate_top_k(value):
    """Contract `Prediction.top_k`: up to 3 {class_id, confidence} items, sorted by confidence, descending."""
    if not isinstance(value, list) or not 1 <= len(value) <= 3:
        raise ValidationError("top_k must be a list of 1 to 3 items.")
    for item in value:
        if not isinstance(item, dict) or set(item) != {"class_id", "confidence"}:
            raise ValidationError("Each top_k item must have exactly class_id and confidence.")
        if not isinstance(item["confidence"], int | float) or not 0 <= item["confidence"] <= 1:
            raise ValidationError("top_k confidence must be between 0 and 1.")
    confidences = [item["confidence"] for item in value]
    if confidences != sorted(confidences, reverse=True):
        raise ValidationError("top_k must be sorted by confidence, highest first.")


def photo_upload_path(instance, filename):
    """Name photos by owner and client id, never the phone's file name (which may hold personal info)."""
    return f"diagnoses/{instance.farmer_id}/{instance.client_id}.jpg"


class Diagnosis(GeoPointMixin):
    """One photo diagnosed on the device. Contract schemas `DiagnosisCreate` / `Diagnosis`.

    The `Prediction` object is stored flattened into columns (rather than one JSON blob) so outbreak reporting
    can filter and count by disease, status and model version directly in SQL.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client_id = models.UUIDField(
        unique=True, help_text="UUIDv4 generated at capture; the sync idempotency key."
    )
    farmer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="diagnoses")
    farm = models.ForeignKey(
        "farms.Farm",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="diagnoses",
        help_text="Optional. Kept as null if the farm is later deleted, so outbreak data isn't lost.",
    )
    crop = models.CharField(
        max_length=20, choices=Crop, help_text="Crop the farmer said they were photographing."
    )
    captured_at = models.DateTimeField(help_text="Device clock at capture. May be wrong; see reported_at.")
    received_at = models.DateTimeField(auto_now_add=True, help_text="Server clock when the sync arrived.")
    app_version = models.CharField(
        max_length=20, blank=True, help_text="PWA version that made the diagnosis."
    )

    # Prediction (contract schema `Prediction`, docs/model-output.md §3)
    disease = models.ForeignKey(
        "catalog.Disease",
        on_delete=models.PROTECT,
        related_name="diagnoses",
        help_text="Top-1 class (`prediction.class_id`). PROTECT: a disease with diagnoses can't be deleted.",
    )
    class_index = models.PositiveSmallIntegerField(
        help_text="`prediction.class_index`, as the model reported it."
    )
    confidence = models.FloatField(validators=PROBABILITY_VALIDATORS, help_text="Top-1 probability, 0 to 1.")
    status = models.CharField(max_length=10, choices=PredictionStatus)
    severity = models.CharField(max_length=10, choices=Severity, default=Severity.UNKNOWN)
    top_k = models.JSONField(
        validators=[validate_top_k], help_text="Up to 3 {class_id, confidence}, highest first."
    )
    model_version = models.CharField(max_length=32, help_text="e.g. 2026.11.0, from labels.json.")
    inference_ms = models.PositiveIntegerField(
        null=True, blank=True, help_text="Shutter-to-result time on the device. Target is 5000 ms or less."
    )

    photo = models.FileField(
        upload_to=photo_upload_path,
        blank=True,
        help_text="Optional leaf photo (JPEG, at most 1 MB), only stored if the farmer gave photo consent.",
    )

    class Meta(GeoPointMixin.Meta):
        verbose_name_plural = "diagnoses"
        ordering = ["-received_at"]
        indexes = [
            models.Index(fields=["farmer", "-received_at"], name="diag_farmer_received_idx"),
            models.Index(fields=["disease", "captured_at"], name="diag_disease_captured_idx"),
        ]
        constraints = [
            *GeoPointMixin.Meta.constraints,
            models.CheckConstraint(
                condition=Q(confidence__gte=0) & Q(confidence__lte=1), name="diag_confidence_0_to_1"
            ),
        ]

    def __str__(self):
        return f"{self.disease_id} ({self.confidence:.0%}) {self.captured_at:%Y-%m-%d}"

    @property
    def has_photo(self):
        """Contract `Diagnosis.has_photo`."""
        return bool(self.photo)

    @property
    def reported_at(self):
        """The time to use in reports. Falls back to `received_at` when the device clock is clearly wrong.

        offline-sync.md, "Clock skew": use captured_at unless it is before 2026-01-01 or more than 30 days
        after received_at.
        """
        if self.captured_at < EARLIEST_PLAUSIBLE_CAPTURE:
            return self.received_at
        if self.received_at and self.captured_at > self.received_at + MAX_CAPTURE_AFTER_RECEIPT:
            return self.received_at
        return self.captured_at

    def clean(self):
        errors = {}
        disease = self.disease if self.disease_id else None
        if disease:
            if disease.crop != self.crop:
                errors["disease"] = f"{disease.class_id} is not a {self.crop} class."
            if disease.class_index != self.class_index:
                errors["class_index"] = (
                    f"{disease.class_id} has index {disease.class_index}, not {self.class_index}."
                )
            if disease.is_healthy and self.severity != Severity.NONE:
                errors["severity"] = "Healthy classes always have severity 'none' (model-output.md §5)."
            if not disease.is_healthy and self.severity == Severity.NONE:
                errors["severity"] = "Only healthy classes can have severity 'none'."
        if isinstance(self.top_k, list) and self.top_k and isinstance(self.top_k[0], dict):
            if self.top_k[0].get("class_id") != self.disease_id:
                errors["top_k"] = "top_k[0] must be the predicted class."
        if self.farm_id and self.farm.owner_id != self.farmer_id:
            errors["farm"] = "That farm belongs to another farmer."
        if errors:
            raise ValidationError(errors)


class Feedback(models.Model):
    """Whether a diagnosis was right, from the farmer or an extension officer. Contract: `FeedbackCreate`.

    Feeds the retraining set: wrong predictions with a corrected class are the most valuable labels we get.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client_id = models.UUIDField(unique=True, help_text="UUIDv4 from the phone; the idempotency key.")
    diagnosis = models.ForeignKey(Diagnosis, on_delete=models.CASCADE, related_name="feedback")
    given_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="feedback_given"
    )
    given_by_role = models.CharField(
        max_length=20,
        choices=Role,
        help_text="Role at the time of the feedback (a farmer may later become an officer).",
    )
    was_correct = models.BooleanField()
    corrected_disease = models.ForeignKey(
        "catalog.Disease",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        help_text="What it actually was, if known. Only allowed when was_correct is false.",
    )
    comment = models.TextField(blank=True, validators=[MaxLengthValidator(500)])
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "feedback"
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(was_correct=False) | Q(corrected_disease__isnull=True),
                name="feedback_correction_only_if_wrong",
            ),
        ]

    def __str__(self):
        verdict = "correct" if self.was_correct else f"wrong -> {self.corrected_disease_id or '?'}"
        return f"{self.diagnosis_id}: {verdict}"

    def clean(self):
        if self.was_correct and self.corrected_disease_id:
            raise ValidationError({"corrected_disease": "Leave empty when the diagnosis was correct."})
