"""Published versions of the on-device model. Contract `GET /model/latest/` and schema `ModelManifest`.

A release is created by `manage.py register_model` from the converted model folder, which checks the files and
the labels before anything is recorded (docs/backend/model-releases.md, ADR 0009). Exactly one release is
**current**: it's the one phones download. Rolling back means making an older release current again.
"""

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models, transaction
from django.db.models import F, Q

MAX_MODEL_BYTES = 15 * 1024 * 1024  # contract ModelManifest.size_bytes maximum (15 MB)

validate_model_version = RegexValidator(
    r"^\d{4}\.\d{1,2}\.\d+$", message="Use YYYY.MM.N, e.g. 2026.11.0.", code="invalid_model_version"
)
validate_app_version = RegexValidator(
    r"^\d+\.\d+\.\d+$", message="Use MAJOR.MINOR.PATCH, e.g. 0.1.0.", code="invalid_app_version"
)
validate_sha256 = RegexValidator(
    r"^[0-9a-f]{64}$", message="64 lowercase hex characters.", code="invalid_sha256"
)


class ModelRelease(models.Model):
    """One converted TensorFlow.js model, published at a versioned CDN path."""

    model_version = models.CharField(
        max_length=32,
        unique=True,
        validators=[validate_model_version],
        help_text="YYYY.MM.N, e.g. 2026.11.0.",
    )
    taxonomy_version = models.CharField(max_length=16, help_text="Taxonomy the model was trained on.")
    model_url = models.URLField(max_length=500, help_text="URL of model.json. Weight shards sit beside it.")
    labels_url = models.URLField(max_length=500, help_text="URL of this model's labels.json.")
    size_bytes = models.PositiveIntegerField(
        validators=[MaxValueValidator(MAX_MODEL_BYTES)], help_text="model.json + all shards. At most 15 MB."
    )
    sha256 = models.CharField(max_length=64, validators=[validate_sha256], help_text="SHA-256 of model.json.")
    threshold_confident = models.FloatField(
        default=0.7,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
        help_text="Confidence at or above this is 'confident' (model-output.md §4, ADR 0002).",
    )
    threshold_uncertain = models.FloatField(
        default=0.4,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
        help_text="Confidence at or above this (and below 'confident') is 'uncertain'; below it, 'consult'.",
    )
    min_app_version = models.CharField(
        max_length=20,
        validators=[validate_app_version],
        help_text="Oldest PWA version that can run this model. Older apps must update first.",
    )
    is_current = models.BooleanField(
        default=False, help_text="The release phones download. Only one at a time."
    )
    notes = models.TextField(blank=True, help_text="Test accuracy, dataset version, what changed.")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["is_current"], condition=Q(is_current=True), name="releases_only_one_current"
            ),
            models.CheckConstraint(
                condition=Q(threshold_uncertain__lt=F("threshold_confident")),
                name="releases_uncertain_below_confident",
            ),
        ]

    def __str__(self):
        return f"{self.model_version}{' (current)' if self.is_current else ''}"

    def clean(self):
        if self.threshold_uncertain is not None and self.threshold_confident is not None:
            if self.threshold_uncertain >= self.threshold_confident:
                raise ValidationError(
                    {"threshold_uncertain": "Must be lower than the 'confident' threshold."}
                )

    def make_current(self):
        """Switch phones to this release. Atomic, so there is never a moment with zero or two current."""
        with transaction.atomic():
            ModelRelease.objects.filter(is_current=True).exclude(pk=self.pk).update(is_current=False)
            ModelRelease.objects.filter(pk=self.pk).update(is_current=True)
        self.is_current = True

    def manifest(self):
        """Contract `ModelManifest`. Also written as manifest.json next to the model files."""
        return {
            "model_version": self.model_version,
            "taxonomy_version": self.taxonomy_version,
            "model_url": self.model_url,
            "labels_url": self.labels_url,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
            "thresholds": {"confident": self.threshold_confident, "uncertain": self.threshold_uncertain},
            "min_app_version": self.min_app_version,
        }
