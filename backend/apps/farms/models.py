"""Farms a farmer grows crops on. Contract schemas `FarmCreate` / `Farm`."""

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from apps.core.choices import Crop
from apps.core.models import GeoPointMixin


def validate_crop_list(value):
    """`crops` is a JSON list (works on SQLite and PostgreSQL alike) of distinct contract `Crop` values."""
    if not isinstance(value, list):
        raise ValidationError("crops must be a list.")
    unknown = sorted(set(value) - set(Crop.values))
    if unknown:
        raise ValidationError(f"Unknown crop(s): {', '.join(map(str, unknown))}.")
    if len(value) != len(set(value)):
        raise ValidationError("crops must not repeat.")


class Farm(GeoPointMixin):
    """A field or plot. Created on the device (possibly offline), so it carries a client-generated id."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client_id = models.UUIDField(
        unique=True, help_text="UUIDv4 generated on the phone; the idempotency key for offline creation."
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="farms",
        help_text="Farmer who owns it.",
    )
    name = models.CharField(
        max_length=80, help_text="The farmer's own name for it, e.g. 'Field by the river'."
    )
    crops = models.JSONField(
        default=list,
        blank=True,
        validators=[validate_crop_list],
        help_text="Crops grown here, e.g. ['maize'].",
    )
    size_hectares = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Optional; farmers often don't know it.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta(GeoPointMixin.Meta):
        ordering = ["name"]

    def __str__(self):
        return self.name
