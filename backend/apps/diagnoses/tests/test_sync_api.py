"""POST /api/v1/diagnoses/sync/, against the rules in docs/offline-sync.md."""

import uuid
from decimal import Decimal

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from apps.core.tests.contract import assert_matches_contract
from apps.core.tests.factories import DiagnosisFactory, FarmerFactory, FarmFactory
from apps.diagnoses.models import Diagnosis

URL = "/api/v1/diagnoses/sync/"


@pytest.fixture(autouse=True)
def _taxonomy(taxonomy):
    """Every sync test needs the real disease classes."""


def item(**overrides):
    """A valid DiagnosisCreate, exactly as the PWA builds it (docs/model-output.md §3)."""
    prediction = {
        "class_id": "maize__grey_leaf_spot",
        "class_index": 2,
        "confidence": 0.91,
        "status": "confident",
        "severity": "moderate",
        "top_k": [
            {"class_id": "maize__grey_leaf_spot", "confidence": 0.91},
            {"class_id": "maize__northern_leaf_blight", "confidence": 0.06},
            {"class_id": "maize__common_rust", "confidence": 0.02},
        ],
        "model_version": "2026.11.0",
        "inference_ms": 1840,
        **overrides.pop("prediction", {}),
    }
    return {
        "client_id": str(uuid.uuid4()),
        "crop": "maize",
        "captured_at": "2026-11-03T09:30:00+02:00",
        "location": None,
        "prediction": prediction,
        "app_version": "0.1.0",
        **overrides,
    }


def sync(api, *items):
    response = api.post(URL, {"items": list(items)}, format="json")
    return response


def results(response):
    assert response.status_code == 200, response.json()
    body = response.json()
    for r in body["results"]:
        assert_matches_contract(r, "SyncResult")
    return body["results"]


class TestCreated:
    def test_creates_a_diagnosis(self, farmer_api, farmer):
        payload = item()
        [r] = results(sync(farmer_api, payload))
        assert r["status"] == "created"
        assert r["client_id"] == payload["client_id"]
        diagnosis = Diagnosis.objects.get(id=r["id"])
        assert diagnosis.farmer == farmer
        assert diagnosis.disease_id == "maize__grey_leaf_spot"
        assert diagnosis.confidence == 0.91
        assert diagnosis.top_k[1] == {"class_id": "maize__northern_leaf_blight", "confidence": 0.06}
        assert diagnosis.app_version == "0.1.0"

    def test_healthy_leaf(self, farmer_api):
        payload = item(
            prediction={
                "class_id": "maize__healthy",
                "class_index": 0,
                "severity": "none",
                "top_k": [{"class_id": "maize__healthy", "confidence": 0.97}],
            }
        )
        [r] = results(sync(farmer_api, payload))
        assert r["status"] == "created"

    def test_a_full_batch_of_25(self, farmer_api):
        rs = results(sync(farmer_api, *[item() for _ in range(25)]))
        assert [r["status"] for r in rs] == ["created"] * 25
        assert Diagnosis.objects.count() == 25

    def test_results_are_in_request_order(self, farmer_api):
        items = [item() for _ in range(5)]
        rs = results(sync(farmer_api, *items))
        assert [r["client_id"] for r in rs] == [i["client_id"] for i in items]

    def test_optional_fields_can_be_left_out(self, farmer_api):
        payload = item()
        for key in ("location", "app_version"):
            del payload[key]
        del payload["prediction"]["inference_ms"]
        [r] = results(sync(farmer_api, payload))
        assert r["status"] == "created"

    def test_linked_to_the_farmers_farm(self, farmer_api, farmer):
        farm = FarmFactory(owner=farmer)
        [r] = results(sync(farmer_api, item(farm_client_id=str(farm.client_id))))
        assert Diagnosis.objects.get(id=r["id"]).farm == farm


class TestIdempotency:
    def test_sending_twice_creates_once(self, farmer_api):
        payload = item()
        [first] = results(sync(farmer_api, payload))
        [second] = results(sync(farmer_api, payload))
        assert (first["status"], second["status"]) == ("created", "duplicate")
        assert second["id"] == first["id"]
        assert Diagnosis.objects.count() == 1

    def test_duplicate_keeps_the_stored_copy(self, farmer_api):
        """Diagnoses are append-only: a resend with different content doesn't change the record."""
        payload = item()
        results(sync(farmer_api, payload))
        changed = {**payload, "prediction": {**payload["prediction"], "confidence": 0.5}}
        [r] = results(sync(farmer_api, changed))
        assert r["status"] == "duplicate"
        assert Diagnosis.objects.get().confidence == 0.91

    def test_duplicate_even_if_the_resend_is_invalid(self, farmer_api):
        payload = item()
        results(sync(farmer_api, payload))
        [r] = results(sync(farmer_api, {**payload, "crop": "rice"}))
        assert r["status"] == "duplicate"

    def test_same_client_id_twice_in_one_batch(self, farmer_api):
        payload = item()
        rs = results(sync(farmer_api, payload, payload))
        assert [r["status"] for r in rs] == ["created", "duplicate"]
        assert rs[0]["id"] == rs[1]["id"]

    def test_another_farmers_client_id_is_a_conflict(self, farmer_api):
        theirs = DiagnosisFactory(farmer=FarmerFactory(phone="+260961111111"))
        [r] = results(sync(farmer_api, item(client_id=str(theirs.client_id))))
        assert r["status"] == "conflict"
        assert r["id"] is None  # never reveal another farmer's record

    def test_mixed_batch(self, farmer_api):
        stored = results(sync(farmer_api, item()))[0]
        theirs = DiagnosisFactory(farmer=FarmerFactory(phone="+260961111111"))
        rs = results(
            sync(
                farmer_api,
                item(),
                item(client_id=stored["client_id"]),
                item(client_id=str(theirs.client_id)),
                item(crop="rice"),
            )
        )
        assert [r["status"] for r in rs] == ["created", "duplicate", "conflict", "invalid"]


RUST_90 = {"class_id": "maize__common_rust", "confidence": 0.9}
GLS_200 = {"class_id": "maize__grey_leaf_spot", "confidence": 2}


class TestInvalid:
    @pytest.mark.parametrize(
        "overrides, field",
        [
            ({"crop": "rice"}, "crop"),
            ({"captured_at": "last tuesday"}, "captured_at"),
            ({"prediction": {"class_id": "maize__alien_blight"}}, "prediction.class_id"),
            ({"prediction": {"confidence": 1.4}}, "prediction.confidence"),
            ({"prediction": {"status": "probably"}}, "prediction.status"),
            ({"prediction": {"class_index": 7}}, "prediction.class_index"),
            ({"prediction": {"severity": "none"}}, "prediction.severity"),
            ({"prediction": {"top_k": []}}, "prediction.top_k"),
            ({"prediction": {"top_k": [RUST_90]}}, "prediction.top_k"),  # top_k[0] isn't the prediction
            ({"prediction": {"top_k": [GLS_200]}}, "prediction.top_k.0.confidence"),
            ({"crop": "cassava"}, "prediction.class_id"),
            ({"farm_client_id": str(uuid.uuid4())}, "farm_client_id"),
        ],
    )  # fmt: skip
    def test_bad_item_is_invalid_with_errors_naming_the_field(self, farmer_api, overrides, field):
        [r] = results(sync(farmer_api, item(**overrides)))
        assert r["status"] == "invalid"
        assert r["id"] is None
        assert field in r["errors"], r["errors"]
        assert not Diagnosis.objects.exists()

    def test_another_farmers_farm_cannot_be_used(self, farmer_api):
        their_farm = FarmFactory(owner=FarmerFactory(phone="+260961111111"))
        [r] = results(sync(farmer_api, item(farm_client_id=str(their_farm.client_id))))
        assert r["status"] == "invalid"
        assert "farm_client_id" in r["errors"]

    def test_one_bad_item_does_not_lose_the_others(self, farmer_api):
        rs = results(sync(farmer_api, item(), item(crop="rice"), item()))
        assert [r["status"] for r in rs] == ["created", "invalid", "created"]
        assert Diagnosis.objects.count() == 2

    def test_an_invalid_item_can_be_fixed_and_resent(self, farmer_api):
        payload = item(crop="rice")
        assert results(sync(farmer_api, payload))[0]["status"] == "invalid"
        [r] = results(sync(farmer_api, {**payload, "crop": "maize"}))
        assert r["status"] == "created"


class TestLocation:
    def test_kept_and_rounded_when_the_farmer_consented(self, farmer_api, farmer):
        farmer.location_consent = True
        farmer.save()
        [r] = results(sync(farmer_api, item(location={"lat": -15.4167891, "lng": 28.2833312})))
        diagnosis = Diagnosis.objects.get(id=r["id"])
        assert (diagnosis.latitude, diagnosis.longitude) == (Decimal("-15.417"), Decimal("28.283"))

    @pytest.mark.parametrize("location", [{"lat": -25.0, "lng": 28.0}, {"lat": -13.0}, [-13.0, 28.0]])
    def test_bad_location_is_invalid(self, farmer_api, farmer, location):
        farmer.location_consent = True
        farmer.save()
        [r] = results(sync(farmer_api, item(location=location)))
        assert r["status"] == "invalid"
        assert "location" in r["errors"], r["errors"]

    def test_dropped_without_consent(self, farmer_api):
        [r] = results(sync(farmer_api, item(location={"lat": -15.417, "lng": 28.283})))
        assert r["status"] == "created"
        assert Diagnosis.objects.get(id=r["id"]).location is None


class TestEnvelope:
    """A malformed request as a whole is a 400; nothing is stored."""

    @pytest.mark.parametrize(
        "body",
        [
            {},
            {"items": []},
            {"items": "not a list"},
            {"items": [{"crop": "maize"}]},  # no client_id: its result couldn't be reported
            {"items": [{"client_id": "not-a-uuid"}]},
        ],
    )
    def test_malformed_batch_is_a_400(self, farmer_api, body):
        response = farmer_api.post(URL, body, format="json")
        assert response.status_code == 400
        assert_matches_contract(response.json(), "Error")
        assert not Diagnosis.objects.exists()

    def test_more_than_25_items_is_a_400(self, farmer_api):
        response = sync(farmer_api, *[item() for _ in range(26)])
        assert response.status_code == 400
        assert "items" in response.json()["fields"]
        assert not Diagnosis.objects.exists()

    def test_requires_a_token(self, db):
        assert APIClient().post(URL, {"items": [item()]}, format="json").status_code == 401


def test_a_full_batch_uses_a_bounded_number_of_queries(farmer_api):
    """25 items must not mean hundreds of queries on a slow rural connection's request."""
    with CaptureQueriesContext(connection) as queries:
        results(sync(farmer_api, *[item() for _ in range(25)]))
    assert len(queries) <= 25 * 3 + 10, len(queries)  # per item: savepoint, insert, release
