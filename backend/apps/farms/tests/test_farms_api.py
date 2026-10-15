"""GET and POST /api/v1/farms/, including client_id idempotency (docs/offline-sync.md)."""

import uuid

import pytest
from rest_framework.test import APIClient

from apps.core.tests.contract import assert_matches_contract
from apps.core.tests.factories import FarmerFactory, FarmFactory
from apps.farms.models import Farm

URL = "/api/v1/farms/"


def new_farm(**overrides):
    return {
        "client_id": str(uuid.uuid4()),
        "name": "Field by the river",
        "crops": ["maize", "groundnut"],
        "size_hectares": 1.5,
        "location": {"lat": -13.633, "lng": 32.65},
        **overrides,
    }


class TestCreate:
    def test_creates_a_farm(self, farmer_api, farmer):
        payload = new_farm()
        response = farmer_api.post(URL, payload, format="json")
        assert response.status_code == 201, response.json()
        body = response.json()
        assert_matches_contract(body, "Farm")
        assert body["client_id"] == payload["client_id"]
        assert body["location"] == {"lat": -13.633, "lng": 32.65}
        assert body["size_hectares"] == 1.5
        assert Farm.objects.get().owner == farmer

    def test_minimal_farm(self, farmer_api):
        response = farmer_api.post(URL, {"client_id": str(uuid.uuid4()), "name": "Home"}, format="json")
        assert response.status_code == 201
        body = response.json()
        assert_matches_contract(body, "Farm")
        assert body["crops"] == [] and body["location"] is None and body["size_hectares"] is None

    def test_sending_the_same_farm_twice_creates_it_once(self, farmer_api):
        payload = new_farm()
        first = farmer_api.post(URL, payload, format="json")
        second = farmer_api.post(URL, {**payload, "name": "Renamed in a retry"}, format="json")
        assert (first.status_code, second.status_code) == (201, 200)
        assert second.json() == first.json()  # the original, unchanged
        assert Farm.objects.count() == 1

    def test_client_id_of_another_farmers_farm_is_a_409(self, farmer_api):
        other = FarmFactory(owner=FarmerFactory(phone="+260961111111"))
        response = farmer_api.post(URL, new_farm(client_id=str(other.client_id)), format="json")
        assert response.status_code == 409
        assert response.json()["code"] == "conflict"
        assert_matches_contract(response.json(), "Error")

    def test_precise_gps_is_rounded_to_about_110_metres(self, farmer_api):
        response = farmer_api.post(
            URL, new_farm(location={"lat": -13.6329871, "lng": 32.6504449}), format="json"
        )
        assert response.json()["location"] == {"lat": -13.633, "lng": 32.65}
        farm = Farm.objects.get()
        assert str(farm.latitude) == "-13.633"

    @pytest.mark.parametrize(
        "overrides, field",
        [
            ({"client_id": "not-a-uuid"}, "client_id"),
            ({"name": ""}, "name"),
            ({"name": "x" * 81}, "name"),
            ({"crops": ["rice"]}, "crops"),
            ({"size_hectares": -1}, "size_hectares"),
            ({"location": {"lat": -25.0, "lng": 28.0}}, "location"),  # South Africa
            ({"location": {"lat": -13.6}}, "location"),
            ({"location": {"lat": "north", "lng": 32.6}}, "location"),
            ({"location": [-13.6, 32.6]}, "location"),
        ],
    )
    def test_invalid_farm_is_a_400_naming_the_field(self, farmer_api, overrides, field):
        response = farmer_api.post(URL, new_farm(**overrides), format="json")
        assert response.status_code == 400, response.json()
        assert_matches_contract(response.json(), "Error")
        assert field in response.json()["fields"], response.json()
        assert not Farm.objects.exists()

    def test_duplicate_crops_are_rejected(self, farmer_api):
        response = farmer_api.post(URL, new_farm(crops=["maize", "maize"]), format="json")
        assert response.status_code == 400
        assert "crops" in response.json()["fields"]

    def test_requires_a_token(self, db):
        assert APIClient().post(URL, new_farm(), format="json").status_code == 401


class TestList:
    def test_lists_only_my_farms(self, farmer_api, farmer):
        FarmFactory(owner=farmer, name="B field")
        FarmFactory(owner=farmer, name="A field")
        FarmFactory(owner=FarmerFactory(phone="+260961111111"), name="Not mine")
        response = farmer_api.get(URL)
        assert response.status_code == 200
        body = response.json()
        assert_matches_contract(body, "Farm", many=True)
        assert [f["name"] for f in body] == ["A field", "B field"]

    def test_empty_list(self, farmer_api):
        assert farmer_api.get(URL).json() == []

    def test_requires_a_token(self, db):
        assert APIClient().get(URL).status_code == 401
