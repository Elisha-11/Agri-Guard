"""Nearby outbreak counts (ADR 0018, contract `GET /alerts/nearby/`).

Rules, in the order they are applied:

1. **Which diagnoses count.** It has a location, its disease is not a healthy class, no extension officer
   marked it wrong, and either the phone reported it `confident` (using that model release's own
   thresholds, ADR 0002) or an extension officer confirmed it. A farmer's own "correct" does not promote an
   uncertain or consult result.
2. **The window** uses the reporting time from docs/offline-sync.md "Clock skew": `captured_at`, unless the
   device clock was clearly wrong, then `received_at` (the same rule as `Diagnosis.reported_at`, in SQL).
3. **The radius** is a cheap latitude/longitude box in SQL, then the exact great-circle distance in Python.
   Locations are two decimal columns, not a PostGIS point (ADR 0004); at MVP volumes the box leaves few rows.
4. **Deduplication:** each farm counts once per disease; a diagnosis without a farm counts once per farmer.
5. **Privacy:** only diseases reported by at least `min_farms` farms are returned, and only as counts.
   Nothing that identifies a farm, a farmer or a location leaves this module.
"""

import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.db.models import Case, DateTimeField, Exists, F, OuterRef, Q, When
from django.utils import timezone

from apps.core.choices import PredictionStatus, Role
from apps.diagnoses.models import EARLIEST_PLAUSIBLE_CAPTURE, MAX_CAPTURE_AFTER_RECEIPT, Diagnosis, Feedback

EARTH_RADIUS_KM = 6371.0088
KM_PER_DEGREE_LAT = 111.32


@dataclass(frozen=True)
class OutbreakConfig:
    radius_km: int
    window_days: int
    min_farms: int

    @classmethod
    def from_settings(cls):
        return cls(
            radius_km=settings.OUTBREAK_RADIUS_KM,
            window_days=settings.OUTBREAK_WINDOW_DAYS,
            min_farms=settings.OUTBREAK_MIN_FARMS,
        )


def distance_km(lat1, lng1, lat2, lng2):
    """Great-circle (haversine) distance between two points, in km."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = phi2 - phi1
    dlmb = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def countable_diagnoses():
    """Diagnoses that may count toward an alert (rule 1), regardless of place and time."""
    officer = Feedback.objects.filter(diagnosis=OuterRef("pk"), given_by_role=Role.EXTENSION_OFFICER)
    return (
        Diagnosis.objects.filter(latitude__isnull=False, longitude__isnull=False, disease__is_healthy=False)
        .annotate(
            officer_confirmed=Exists(officer.filter(was_correct=True)),
            officer_rejected=Exists(officer.filter(was_correct=False)),
        )
        .filter(Q(status=PredictionStatus.CONFIDENT) | Q(officer_confirmed=True))
        .exclude(officer_rejected=True)
    )


def reported_at_expression():
    """`Diagnosis.reported_at` as SQL (docs/offline-sync.md, "Clock skew")."""
    clock_ok = Q(captured_at__gte=EARLIEST_PLAUSIBLE_CAPTURE) & Q(
        captured_at__lte=F("received_at") + MAX_CAPTURE_AFTER_RECEIPT
    )
    return Case(When(clock_ok, then=F("captured_at")), default=F("received_at"), output_field=DateTimeField())


def nearby_alerts(lat, lng, *, config=None, now=None):
    """Aggregate alerts around (lat, lng). Returns the contract `NearbyAlerts` object."""
    config = config or OutbreakConfig.from_settings()
    now = now or timezone.now()
    since = now - timedelta(days=config.window_days)

    dlat = config.radius_km / KM_PER_DEGREE_LAT
    # Longitude degrees shrink towards the poles; Zambia is at 8-18 degrees south, so this stays well defined.
    dlng = config.radius_km / (KM_PER_DEGREE_LAT * max(math.cos(math.radians(lat)), 0.01))

    rows = (
        countable_diagnoses()
        .annotate(reported=reported_at_expression())
        .filter(
            reported__gte=since,
            reported__lte=now,
            latitude__range=(lat - dlat, lat + dlat),
            longitude__range=(lng - dlng, lng + dlng),
        )
        .values_list("disease_id", "farm_id", "farmer_id", "latitude", "longitude")
    )

    reporters = defaultdict(set)  # class_id -> distinct farms (or farmers without a farm)
    for class_id, farm_id, farmer_id, d_lat, d_lng in rows:
        if distance_km(lat, lng, float(d_lat), float(d_lng)) > config.radius_km:
            continue
        reporters[class_id].add(("farm", farm_id) if farm_id else ("farmer", farmer_id))

    alerts = [
        {
            "class_id": class_id,
            "farm_count": len(farms),
            "distance_band_km": config.radius_km,
            "window_days": config.window_days,
        }
        for class_id, farms in reporters.items()
        if len(farms) >= config.min_farms
    ]
    alerts.sort(key=lambda alert: (-alert["farm_count"], alert["class_id"]))

    return {
        "generated_at": now.isoformat().replace("+00:00", "Z"),
        "radius_km": config.radius_km,
        "window_days": config.window_days,
        "min_farms": config.min_farms,
        "alerts": alerts,
    }
