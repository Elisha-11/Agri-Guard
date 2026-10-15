"""Abstract building blocks reused by concrete models in other apps."""

from django.db import models
from django.db.models import Q

from .validators import LATITUDE_VALIDATORS, LONGITUDE_VALIDATORS


class GeoPointMixin(models.Model):
    """Optional location stored as two decimals rather than a PostGIS point (see ADR 0004).

    The contract's `GeoPoint` is rounded on the device to 3 decimal places (~110 m) so a homestead can't be
    pinpointed; three decimal places here means the database can't hold anything more precise either.
    """

    latitude = models.DecimalField(
        max_digits=6,
        decimal_places=3,
        null=True,
        blank=True,
        validators=LATITUDE_VALIDATORS,
        help_text="Degrees, rounded to 3 dp (~110 m). Must be inside Zambia (-18.1 to -8.2).",
    )
    longitude = models.DecimalField(
        max_digits=6,
        decimal_places=3,
        null=True,
        blank=True,
        validators=LONGITUDE_VALIDATORS,
        help_text="Degrees, rounded to 3 dp (~110 m). Must be inside Zambia (21.9 to 33.8).",
    )

    class Meta:
        abstract = True
        constraints = [
            models.CheckConstraint(
                condition=Q(latitude__isnull=True, longitude__isnull=True)
                | Q(latitude__isnull=False, longitude__isnull=False),
                name="%(app_label)s_%(class)s_location_both_or_neither",
            ),
        ]

    @property
    def location(self):
        """The contract's `GeoPoint` shape, or None."""
        if self.latitude is None:
            return None
        return {"lat": float(self.latitude), "lng": float(self.longitude)}
