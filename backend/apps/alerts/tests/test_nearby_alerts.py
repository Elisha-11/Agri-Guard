"""`GET /alerts/nearby/` (ADR 0018): radius, window, deduplication, confidence filter and privacy."""

import json
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.alerts.outbreaks import distance_km
from apps.core.tests.contract import assert_matches_contract
from apps.core.tests.factories import DiagnosisFactory, FarmerFactory, FarmFactory, FeedbackFactory
from apps.diagnoses.models import Diagnosis

URL = "/api/v1/alerts/nearby/"
HOME = (-15.400, 28.300)  # Lusaka area
GLS = "maize__grey_leaf_spot"
RUST = "maize__common_rust"


def north(km):
    """A point `km` due north of HOME, rounded to 3 dp like the phone does (~110 m)."""
    return (round(HOME[0] + km / 111.195, 3), HOME[1])


def report(*, farm=None, farmer=None, at=HOME, disease=GLS, status="confident", days_ago=1, **extra):
    """One synced diagnosis. A new farm (and farmer) unless one is given."""
    if farm is None and farmer is None:
        farm = FarmFactory()
    farmer = farmer or farm.owner
    index = {GLS: 2, RUST: 3, "maize__healthy": 0}[disease]
    return DiagnosisFactory(
        farmer=farmer,
        farm=farm,
        latitude=Decimal(str(at[0])) if at else None,
        longitude=Decimal(str(at[1])) if at else None,
        disease_id=disease,
        class_index=index,
        severity="none" if disease == "maize__healthy" else "unknown",
        top_k=[{"class_id": disease, "confidence": 0.9}],
        status=status,
        captured_at=timezone.now() - timedelta(days=days_ago),
        **extra,
    )


def alerts(at=HOME):
    response = APIClient().get(URL, {"lat": at[0], "lng": at[1]})
    assert response.status_code == 200, response.content
    return response


def counts(at=HOME):
    return {a["class_id"]: a["farm_count"] for a in alerts(at).json()["alerts"]}


pytestmark = pytest.mark.usefixtures("taxonomy")


# --------------------------------------------------------------- threshold


def test_three_farms_make_an_alert_and_two_do_not():
    report()
    report()
    assert counts() == {}
    report()
    assert counts() == {GLS: 3}


@override_settings(OUTBREAK_MIN_FARMS=2)
def test_minimum_farms_comes_from_settings():
    report()
    report()
    assert counts() == {GLS: 2}


def test_each_disease_is_counted_separately_and_ordered_by_farm_count():
    for _ in range(4):
        report(disease=RUST)
    for _ in range(3):
        report()
    body = alerts().json()
    assert [(a["class_id"], a["farm_count"]) for a in body["alerts"]] == [(RUST, 4), (GLS, 3)]


# ------------------------------------------------------------------ radius


def test_radius_boundary():
    inside, outside = north(9.8), north(10.4)
    assert distance_km(*HOME, *inside) < 10 < distance_km(*HOME, *outside)

    report(at=inside)
    report(at=inside)
    report(at=outside)
    assert counts() == {}  # only two farms inside 10 km

    report(at=inside)
    assert counts() == {GLS: 3}


@override_settings(OUTBREAK_RADIUS_KM=20)
def test_radius_comes_from_settings():
    for _ in range(3):
        report(at=north(15))
    body = alerts().json()
    assert body["radius_km"] == 20
    assert body["alerts"][0]["distance_band_km"] == 20


def test_diagnoses_without_a_location_never_count():
    for _ in range(3):
        report(at=None)
    assert counts() == {}


# ------------------------------------------------------------------ window


def test_window_boundary():
    report(days_ago=6)
    report(days_ago=6)
    report(days_ago=8)  # outside the 7-day window
    assert counts() == {}
    report(days_ago=1)
    assert counts() == {GLS: 3}


@override_settings(OUTBREAK_WINDOW_DAYS=14)
def test_window_comes_from_settings():
    for _ in range(3):
        report(days_ago=10)
    assert counts() == {GLS: 3}


def test_a_wrong_device_clock_falls_back_to_received_at():
    """offline-sync.md "Clock skew": a capture date before 2026 means the phone clock was wrong."""
    recent = [report(), report()]
    bad_clock = report()
    Diagnosis.objects.filter(pk=bad_clock.pk).update(captured_at=datetime(2020, 1, 1, tzinfo=UTC))
    assert counts() == {GLS: 3}  # received today, so it is recent

    # And an old diagnosis whose phone clock says "now" is judged by when it arrived.
    Diagnosis.objects.filter(pk__in=[d.pk for d in recent]).update(
        received_at=timezone.now() - timedelta(days=40), captured_at=timezone.now()
    )
    assert counts() == {}


# --------------------------------------------------------------- dedup


def test_one_farm_scanning_ten_times_counts_once():
    busy = FarmFactory()
    for _ in range(10):
        report(farm=busy)
    assert counts() == {}

    report()
    report()
    assert counts() == {GLS: 3}


def test_diagnoses_without_a_farm_count_once_per_farmer():
    farmer = FarmerFactory()
    for _ in range(5):
        report(farmer=farmer)
    report(farmer=FarmerFactory())
    assert counts() == {}  # two farmers
    report(farmer=FarmerFactory())
    assert counts() == {GLS: 3}


# ------------------------------------------------------- confidence filter


def officer():
    return FarmerFactory(role="extension_officer")


def test_uncertain_and_consult_results_do_not_count():
    report(status="uncertain")
    report(status="consult")
    report()
    report()
    assert counts() == {}


def test_an_officer_confirmation_makes_an_uncertain_result_count():
    confirmed = report(status="uncertain")
    report()
    report()
    assert counts() == {}
    FeedbackFactory(
        diagnosis=confirmed, given_by=officer(), given_by_role="extension_officer", was_correct=True
    )
    assert counts() == {GLS: 3}


def test_a_farmers_own_confirmation_does_not_promote_an_uncertain_result():
    mine = report(status="uncertain")
    FeedbackFactory(diagnosis=mine, was_correct=True)  # given by the farmer
    report()
    report()
    assert counts() == {}


def test_an_officer_marking_it_wrong_removes_even_a_confident_result():
    wrong = report()
    report()
    report()
    assert counts() == {GLS: 3}
    FeedbackFactory(diagnosis=wrong, given_by=officer(), given_by_role="extension_officer", was_correct=False)
    assert counts() == {}


def test_healthy_classes_never_alert():
    for _ in range(3):
        report(disease="maize__healthy")
    assert counts() == {}


# ----------------------------------------------------------------- privacy


def test_response_is_aggregate_only_and_matches_the_contract():
    farms = [report(), report(), report()]
    response = alerts()
    body = response.json()
    assert_matches_contract(body, "NearbyAlerts")
    assert set(body) == {"generated_at", "radius_km", "window_days", "min_farms", "alerts"}
    assert set(body["alerts"][0]) == {"class_id", "farm_count", "distance_band_km", "window_days"}

    raw = response.content.decode()
    for diagnosis in farms:
        for secret in (
            diagnosis.farm_id,
            diagnosis.farm.client_id,
            diagnosis.farmer_id,
            diagnosis.farmer.phone,
            diagnosis.id,
            diagnosis.client_id,
            str(diagnosis.latitude),
            str(diagnosis.longitude),
        ):
            assert str(secret) not in raw
    for word in ("farm_id", "farmer", "phone", "latitude", "longitude", "client_id"):
        assert word not in raw


def test_below_the_minimum_nothing_about_the_disease_is_revealed():
    report()
    report()
    raw = alerts().content.decode()
    assert GLS not in raw
    assert json.loads(raw)["alerts"] == []


def test_it_is_public_and_not_cached_by_intermediaries():
    response = alerts()
    assert response["Cache-Control"] == "no-cache"


# -------------------------------------------------------------- validation


@pytest.mark.parametrize(
    "query",
    [
        {},
        {"lat": HOME[0]},
        {"lat": "x", "lng": HOME[1]},
        {"lat": 51.5, "lng": -0.12},
        {"lat": -15.4, "lng": 40},
    ],
)
def test_bad_coordinates_are_a_400_in_the_contract_error_shape(query):
    response = APIClient().get(URL, query)
    assert response.status_code == 400
    assert_matches_contract(response.json(), "Error")


def test_unused_ids_do_not_leak_through_errors():
    response = APIClient().get(URL, {"lat": str(uuid.uuid4()), "lng": HOME[1]})
    assert response.status_code == 400
