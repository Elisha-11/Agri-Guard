"""GET /api/v1/diagnoses/: the farmer's history, newest first, cursor-paginated, with `since`."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.tests.contract import assert_matches_contract
from apps.core.tests.factories import DiagnosisFactory, FarmerFactory, FarmFactory
from apps.diagnoses.models import Diagnosis

URL = "/api/v1/diagnoses/"


@pytest.fixture(autouse=True)
def _taxonomy(taxonomy):
    """Every history test needs the real disease classes."""


def page(api, url=URL, **params):
    response = api.get(url, params)
    assert response.status_code == 200, response.json()
    body = response.json()
    assert set(body) == {"next", "results"}
    for item in body["results"]:
        assert_matches_contract(item, "Diagnosis")
    return body


def received(diagnosis, moment):
    """received_at is set by the database on insert; tests move it to control ordering."""
    Diagnosis.objects.filter(pk=diagnosis.pk).update(received_at=moment)


class TestContent:
    def test_rebuilds_what_the_phone_sent(self, farmer_api, farmer):
        """Sync an item, read it back from history: the phone gets the same object it stored."""
        farmer.location_consent = True
        farmer.save()
        farm = FarmFactory(owner=farmer)
        item = {
            "client_id": "2f1b8a4e-3c2d-4e5f-9a6b-7c8d9e0f1a2b",
            "farm_client_id": str(farm.client_id),
            "crop": "maize",
            "captured_at": "2026-11-03T09:30:00+02:00",
            "location": {"lat": -13.633, "lng": 32.65},
            "prediction": {
                "class_id": "maize__grey_leaf_spot",
                "class_index": 2,
                "confidence": 0.91,
                "status": "confident",
                "severity": "moderate",
                "top_k": [
                    {"class_id": "maize__grey_leaf_spot", "confidence": 0.91},
                    {"class_id": "maize__common_rust", "confidence": 0.05},
                ],
                "model_version": "2026.11.0",
                "inference_ms": 1840,
            },
            "app_version": "0.1.0",
        }
        assert farmer_api.post("/api/v1/diagnoses/sync/", {"items": [item]}, format="json").status_code == 200

        [restored] = page(farmer_api)["results"]
        for key in ("client_id", "farm_client_id", "crop", "location", "prediction", "app_version"):
            assert restored[key] == item[key], key
        assert restored["has_photo"] is False
        assert restored["id"] and restored["received_at"]

    def test_no_farm_and_no_location_are_null(self, farmer_api, farmer):
        DiagnosisFactory(farmer=farmer)
        [item] = page(farmer_api)["results"]
        assert item["farm_client_id"] is None
        assert item["location"] is None

    def test_only_my_diagnoses(self, farmer_api, farmer):
        mine = DiagnosisFactory(farmer=farmer)
        DiagnosisFactory(farmer=FarmerFactory(phone="+260961111111"))
        assert [d["client_id"] for d in page(farmer_api)["results"]] == [str(mine.client_id)]

    def test_newest_first(self, farmer_api, farmer):
        now = timezone.now()
        old, new, middle = (DiagnosisFactory(farmer=farmer) for _ in range(3))
        received(old, now - timedelta(days=2))
        received(middle, now - timedelta(days=1))
        received(new, now)
        assert [d["client_id"] for d in page(farmer_api)["results"]] == [
            str(new.client_id),
            str(middle.client_id),
            str(old.client_id),
        ]

    def test_empty_history(self, farmer_api):
        assert page(farmer_api) == {"next": None, "results": []}


class TestPaging:
    def test_follows_next_through_every_page_without_gaps_or_repeats(self, farmer_api, farmer):
        created = {str(DiagnosisFactory(farmer=farmer).client_id) for _ in range(230)}
        seen, url, pages = [], URL, 0
        while url:
            body = page(farmer_api, url)
            seen += [d["client_id"] for d in body["results"]]
            url, pages = body["next"], pages + 1
        assert pages == 3  # 100 + 100 + 30
        assert len(seen) == len(set(seen)) == 230
        assert set(seen) == created

    def test_ties_on_received_at_are_still_paged_exactly_once(self, farmer_api, farmer):
        """A synced batch can land in the same instant."""
        same_moment = timezone.now()
        diagnoses = [DiagnosisFactory(farmer=farmer) for _ in range(150)]
        Diagnosis.objects.filter(pk__in=[d.pk for d in diagnoses]).update(received_at=same_moment)
        first = page(farmer_api)
        second = page(farmer_api, first["next"])
        ids = [d["client_id"] for d in first["results"] + second["results"]]
        assert len(ids) == len(set(ids)) == 150
        assert second["next"] is None

    def test_new_arrivals_while_paging_do_not_shift_pages(self, farmer_api, farmer):
        for _ in range(150):
            DiagnosisFactory(farmer=farmer)
        first = page(farmer_api)
        DiagnosisFactory(farmer=farmer)  # synced from another device mid-restore
        second = page(farmer_api, first["next"])
        ids = [d["client_id"] for d in first["results"] + second["results"]]
        assert len(ids) == len(set(ids)) == 150

    def test_bad_cursor_is_a_400(self, farmer_api):
        response = farmer_api.get(URL, {"cursor": "garbage"})
        assert response.status_code == 400
        assert_matches_contract(response.json(), "Error")
        assert "cursor" in response.json()["fields"]

    def test_a_page_uses_a_fixed_number_of_queries(self, farmer_api, farmer):
        for _ in range(100):
            DiagnosisFactory(farmer=farmer, farm=FarmFactory(owner=farmer))
        with CaptureQueriesContext(connection) as queries:
            page(farmer_api)
        assert len(queries) <= 3, [q["sql"] for q in queries]  # user lookup + one page query (farms joined)


class TestSince:
    def test_only_what_arrived_after(self, farmer_api, farmer):
        now = timezone.now()
        old, new = DiagnosisFactory(farmer=farmer), DiagnosisFactory(farmer=farmer)
        received(old, now - timedelta(days=3))
        received(new, now)
        body = page(farmer_api, since=(now - timedelta(days=1)).isoformat())
        assert [d["client_id"] for d in body["results"]] == [str(new.client_id)]

    def test_since_is_exclusive(self, farmer_api, farmer):
        """Passing the newest received_at the phone has returns nothing new, not that item again."""
        diagnosis = DiagnosisFactory(farmer=farmer)
        [item] = page(farmer_api)["results"]
        assert page(farmer_api, since=item["received_at"])["results"] == []
        assert Diagnosis.objects.filter(pk=diagnosis.pk).exists()

    def test_since_works_with_paging(self, farmer_api, farmer):
        now = timezone.now()
        for d in [DiagnosisFactory(farmer=farmer) for _ in range(120)]:
            received(d, now)
        old = DiagnosisFactory(farmer=farmer)
        received(old, now - timedelta(days=5))
        first = page(farmer_api, since=(now - timedelta(days=1)).isoformat())
        second = page(farmer_api, first["next"])
        assert len(first["results"]) + len(second["results"]) == 120

    @pytest.mark.parametrize("since", ["yesterday", "2026-13-45"])
    def test_bad_since_is_a_400(self, farmer_api, since):
        response = farmer_api.get(URL, {"since": since})
        assert response.status_code == 400
        assert "since" in response.json()["fields"]


def test_requires_a_token(db):
    assert APIClient().get(URL).status_code == 401


def test_location_is_returned_as_stored(farmer_api, farmer):
    DiagnosisFactory(farmer=farmer, latitude=Decimal("-15.417"), longitude=Decimal("28.283"))
    assert page(farmer_api)["results"][0]["location"] == {"lat": -15.417, "lng": 28.283}
