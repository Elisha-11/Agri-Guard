"""The disease catalogue (what the model can recognise) and the advice shown for each disease, per language.

`Disease` rows come from ml/labels.json via `manage.py load_taxonomy`, never typed by hand, so the backend
and the model always agree on class ids and indices. `DiseaseAdvice` rows are written by agronomists in the
admin and served to the PWA as the advisory bundle (contract `GET /advisory/bundle/`).
"""

from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Q

from apps.core.choices import Crop, Language

validate_class_id = RegexValidator(
    r"^[a-z]+__[a-z_]+$", message="Use <crop>__<condition> in lowercase snake_case.", code="invalid_class_id"
)


class Disease(models.Model):
    """One output class of the model, healthy classes included. Mirrors one entry of labels.json `classes`.

    The primary key is the class id string (ADR 0005): it's what the PWA sends in a prediction, so a diagnosis
    can be validated and stored without a lookup table, and it stays readable in the database and the admin.
    """

    class_id = models.CharField(
        primary_key=True,
        max_length=64,
        validators=[validate_class_id],
        help_text="Stable id, e.g. maize__grey_leaf_spot. Never renamed once used in a released model.",
    )
    class_index = models.PositiveSmallIntegerField(
        unique=True,
        help_text="Position in the model's output tensor. Fixed forever (class-taxonomy.md rules).",
    )
    crop = models.CharField(max_length=20, choices=Crop)
    is_healthy = models.BooleanField(default=False, help_text="The '<crop>__healthy' class for this crop.")
    is_retired = models.BooleanField(
        default=False,
        help_text=(
            "No longer predicted by current models. " "Kept so old diagnoses and indices keep their meaning."
        ),
    )
    taxonomy_version = models.CharField(
        max_length=16, help_text="Taxonomy version this row was last loaded from."
    )

    class Meta:
        ordering = ["class_index"]

    def __str__(self):
        return self.class_id

    def clean(self):
        if self.class_id and self.crop and not self.class_id.startswith(f"{self.crop}__"):
            raise ValidationError({"class_id": f"Must start with '{self.crop}__' to match the crop."})
        if self.class_id and self.is_healthy != self.class_id.endswith("__healthy"):
            raise ValidationError({"is_healthy": "Only '<crop>__healthy' classes are healthy."})


def validate_string_list(value):
    if not isinstance(value, list) or not all(isinstance(s, str) and s.strip() for s in value):
        raise ValidationError("Must be a list of non-empty strings.")


def validate_advice_section(value):
    """Contract schema `AdviceSection`: {"title": str, "steps": [str], "audio_url": str | null}."""
    if not isinstance(value, dict):
        raise ValidationError("Must be an object with title, steps and audio_url.")
    unknown = set(value) - {"title", "steps", "audio_url"}
    if unknown:
        raise ValidationError(f"Unknown key(s): {', '.join(sorted(unknown))}.")
    if not isinstance(value.get("title"), str) or not value["title"].strip():
        raise ValidationError("title is required.")
    validate_string_list(value.get("steps"))
    if value.get("audio_url") is not None and not isinstance(value["audio_url"], str):
        raise ValidationError("audio_url must be a URL string or null.")


def empty_section():
    return {"title": "", "steps": [], "audio_url": None}


class DiseaseAdvice(models.Model):
    """The farmer-facing text for one disease in one language. Contract schema `DiseaseAdvice`.

    Only published rows reach farmers, and a row can't be published until an agronomist is recorded as having
    reviewed it. Treatment advice can cause real harm if wrong, so this is enforced in the database.
    """

    disease = models.ForeignKey(Disease, on_delete=models.CASCADE, related_name="advice")
    lang = models.CharField(max_length=3, choices=Language)
    name = models.CharField(max_length=120, help_text="Display name in this language, e.g. 'Grey Leaf Spot'.")
    local_name = models.CharField(
        max_length=120, blank=True, help_text="What farmers in the area call it, if different from the name."
    )
    symptoms = models.JSONField(
        default=list,
        validators=[validate_string_list],
        help_text="List of short sentences: what to look for.",
    )
    treatment = models.JSONField(
        default=empty_section,
        validators=[validate_advice_section],
        help_text="Immediate action. AdviceSection.",
    )
    prevention = models.JSONField(
        default=empty_section, validators=[validate_advice_section], help_text="Next season. AdviceSection."
    )
    follow_up = models.JSONField(
        default=empty_section, validators=[validate_advice_section], help_text="What to check and when."
    )
    involves_chemicals = models.BooleanField(
        default=False, help_text="Tick if the treatment mentions any pesticide, fungicide or herbicide."
    )
    safety_warning = models.TextField(
        blank=True,
        help_text="Required when chemicals are involved: protective equipment, dosage, pre-harvest interval.",
    )
    reviewed_by = models.CharField(
        max_length=120, blank=True, help_text="Agronomist who signed off this text."
    )
    reviewed_at = models.DateField(null=True, blank=True)
    is_published = models.BooleanField(
        default=False,
        help_text="Include in the advisory bundle sent to phones. Needs reviewed_by and reviewed_at.",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "disease advice"
        verbose_name_plural = "disease advice"
        ordering = ["disease__class_index", "lang"]
        constraints = [
            models.UniqueConstraint(fields=["disease", "lang"], name="catalog_advice_one_per_language"),
            models.CheckConstraint(
                condition=Q(is_published=False) | (~Q(reviewed_by="") & Q(reviewed_at__isnull=False)),
                name="catalog_advice_published_needs_review",
            ),
            models.CheckConstraint(
                condition=Q(involves_chemicals=False) | ~Q(safety_warning=""),
                name="catalog_advice_chemicals_need_warning",
            ),
        ]

    def __str__(self):
        return f"{self.disease_id} [{self.lang}]"

    def clean(self):
        errors = {}
        if self.is_published and not (self.reviewed_by and self.reviewed_at):
            errors["is_published"] = "Record who reviewed this text, and when, before publishing it."
        if self.involves_chemicals and not self.safety_warning.strip():
            errors["safety_warning"] = "A safety warning is required whenever chemicals are involved."
        if errors:
            raise ValidationError(errors)


class UiMessage(models.Model):
    """A fixed message the PWA shows when it can't give a confident diagnosis. Contract `AdvisoryBundle.ui`.

    These are safety messages ("show this plant to an extension officer"), so they are editable content
    reviewed like advice, not strings hard-coded in the app. English defaults are created by a data
    migration. Another language falls back to English, key by key, until it's translated.
    """

    class Key(models.TextChoices):
        UNCERTAIN = "uncertain", "Uncertain: ask for another photo (model-output.md §4)"
        CONSULT = "consult", "Consult: send to an extension officer, no treatment advice"
        REJECTED = "rejected", "Rejected: photo failed quality checks, retake"
        NO_ADVICE = "no_advice", "Diagnosis has no reviewed advice yet"

    key = models.CharField(max_length=20, choices=Key)
    lang = models.CharField(max_length=3, choices=Language)
    text = models.TextField(help_text="Short and plain. Read aloud by voice narration.")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "app message"
        ordering = ["key", "lang"]
        constraints = [
            models.UniqueConstraint(fields=["key", "lang"], name="catalog_uimessage_one_per_language")
        ]

    def __str__(self):
        return f"{self.key} [{self.lang}]"
