"""GET and PATCH /api/v1/me/, including last-write-wins (docs/offline-sync.md)."""

from datetime import timedelta
from unittest import mock

import pytest
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.tests.contract import assert_matches_contract

URL = "/api/v1/me/"


def iso(moment):
    return moment.isoformat()


class TestGetProfile:
    def test_returns_the_contract_farmer_shape(self, farmer_api, farmer):
        response = farmer_api.get(URL)
        assert response.status_code == 200
        body = response.json()
        assert_matches_contract(body, "Farmer")
        assert body["id"] == str(farmer.id)
        assert body["phone"] == "+260971234567"

    def test_empty_text_fields_are_null(self, farmer_api):
        body = farmer_api.get(URL).json()
        assert body["display_name"] is None
        assert body["province"] is None
        assert body["district"] is None

    def test_requires_a_token(self, db):
        response = APIClient().get(URL)
        assert response.status_code == 401
        assert response.json()["code"] == "not_authenticated"
        assert_matches_contract(response.json(), "Error")

    def test_rejects_a_bad_token(self, db):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer not-a-token")
        response = client.get(URL)
        assert response.status_code == 401
        assert_matches_contract(response.json(), "Error")

    def test_blocked_farmer_is_refused_even_with_a_valid_token(self, farmer):
        token = RefreshToken.for_user(farmer).access_token
        farmer.is_active = False
        farmer.save()
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        assert client.get(URL).status_code == 401

    def test_a_refresh_token_cannot_be_used_as_an_access_token(self, farmer):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(farmer)}")
        assert client.get(URL).status_code == 401


class TestUpdateProfile:
    def test_updates_fields(self, farmer_api, farmer):
        response = farmer_api.patch(
            URL,
            {
                "display_name": "Mrs Banda",
                "preferred_language": "ny",
                "province": "Eastern",
                "district": "Chipata",
                "photo_consent": True,
                "location_consent": True,
            },
            format="json",
        )
        assert response.status_code == 200
        body = response.json()
        assert_matches_contract(body, "Farmer")
        assert body["display_name"] == "Mrs Banda"
        assert body["preferred_language"] == "ny"
        farmer.refresh_from_db()
        assert farmer.district == "Chipata" and farmer.photo_consent

    def test_partial_update_leaves_other_fields_alone(self, farmer_api, farmer):
        farmer_api.patch(URL, {"display_name": "Mrs Banda", "district": "Chipata"}, format="json")
        farmer_api.patch(URL, {"district": "Lundazi"}, format="json")
        farmer.refresh_from_db()
        assert (farmer.display_name, farmer.district) == ("Mrs Banda", "Lundazi")

    def test_null_clears_a_text_field(self, farmer_api, farmer):
        farmer_api.patch(URL, {"display_name": "Mrs Banda"}, format="json")
        body = farmer_api.patch(URL, {"display_name": None}, format="json").json()
        assert body["display_name"] is None
        farmer.refresh_from_db()
        assert farmer.display_name == ""

    def test_phone_and_role_cannot_be_changed(self, farmer_api, farmer):
        farmer_api.patch(URL, {"phone": "+260961111111", "role": "extension_officer"}, format="json")
        farmer.refresh_from_db()
        assert farmer.phone == "+260971234567"
        assert farmer.role == "farmer"

    @pytest.mark.parametrize(
        "payload, field",
        [
            ({"preferred_language": "fr"}, "preferred_language"),
            ({"display_name": "x" * 81}, "display_name"),
            ({"photo_consent": "maybe"}, "photo_consent"),
            ({"updated_at": "yesterday"}, "updated_at"),
        ],
    )
    def test_invalid_values_are_a_400(self, farmer_api, payload, field):
        response = farmer_api.patch(URL, payload, format="json")
        assert response.status_code == 400
        assert_matches_contract(response.json(), "Error")
        assert field in response.json()["fields"]


class TestLastWriteWins:
    def test_newer_edit_wins(self, farmer_api, farmer):
        edited = timezone.now() - timedelta(minutes=5)
        farmer.updated_at = edited - timedelta(days=1)
        farmer.save()
        body = farmer_api.patch(URL, {"district": "Chipata", "updated_at": iso(edited)}, format="json").json()
        assert body["district"] == "Chipata"
        farmer.refresh_from_db()
        assert farmer.updated_at == edited

    def test_older_offline_edit_is_ignored_and_the_current_profile_returned(self, farmer_api, farmer):
        farmer_api.patch(URL, {"district": "Lundazi"}, format="json")  # edit "now" on another phone
        stale = timezone.now() - timedelta(days=3)  # made offline three days ago, synced only now
        response = farmer_api.patch(URL, {"district": "Chipata", "updated_at": iso(stale)}, format="json")
        assert response.status_code == 200
        assert response.json()["district"] == "Lundazi"

    def test_future_timestamp_is_clamped_to_now(self, farmer_api, farmer):
        future = timezone.now() + timedelta(days=30)  # phone clock a month fast
        farmer_api.patch(URL, {"district": "Chipata", "updated_at": iso(future)}, format="json")
        farmer.refresh_from_db()
        assert farmer.updated_at <= timezone.now()
        # ...so a genuine edit a moment later still goes through.
        farmer_api.patch(URL, {"district": "Lundazi"}, format="json")
        farmer.refresh_from_db()
        assert farmer.district == "Lundazi"

    def test_quick_successive_edits_all_apply(self, farmer_api, farmer):
        """Regression: edits in the same clock tick were dropped as 'not newer' (flaky on Windows)."""
        with mock.patch("apps.accounts.views.timezone.now", return_value=farmer.updated_at + timedelta(hours=1)):
            for district in ["Chipata", "Lundazi", "Petauke"]:
                farmer_api.patch(URL, {"district": district}, format="json")
        farmer.refresh_from_db()
        assert farmer.district == "Petauke"

    def test_no_timestamp_means_now(self, farmer_api, farmer):
        before = farmer.updated_at
        farmer_api.patch(URL, {"district": "Chipata"}, format="json")
        farmer.refresh_from_db()
        assert farmer.updated_at > before
