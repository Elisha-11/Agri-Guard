"""POST /api/v1/feedback/: who may give feedback, idempotency, and corrections."""

import uuid

import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.tests.contract import assert_matches_contract
from apps.core.tests.factories import DiagnosisFactory, FarmerFactory
from apps.diagnoses.models import Feedback

URL = "/api/v1/feedback/"


@pytest.fixture
def diagnosis(taxonomy, farmer):
    return DiagnosisFactory(farmer=farmer)


def signed_in(user):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}")
    return client


def payload(diagnosis, **overrides):
    body = {
        "client_id": str(uuid.uuid4()),
        "diagnosis_client_id": str(diagnosis.client_id),
        "was_correct": True,
        **overrides,
    }
    assert_matches_contract(body, "FeedbackCreate")  # the tests send only what the contract allows
    return body


def post(client, body):
    return client.post(URL, body, format="json")


class TestCreate:
    def test_farmer_confirms_their_diagnosis(self, farmer_api, farmer, diagnosis):
        body = payload(diagnosis)
        response = post(farmer_api, body)
        assert response.status_code == 201, response.json()
        assert response.json()["client_id"] == body["client_id"]
        feedback = Feedback.objects.get(id=response.json()["id"])
        assert feedback.diagnosis == diagnosis
        assert feedback.given_by == farmer
        assert feedback.given_by_role == "farmer"
        assert feedback.was_correct and feedback.corrected_disease is None

    def test_correction_with_the_real_class(self, farmer_api, diagnosis):
        body = payload(
            diagnosis, was_correct=False, corrected_class_id="maize__common_rust", comment=" Rust "
        )
        response = post(farmer_api, body)
        assert response.status_code == 201
        feedback = Feedback.objects.get()
        assert feedback.corrected_disease_id == "maize__common_rust"
        assert feedback.comment == "Rust"

    def test_wrong_without_knowing_the_real_class(self, farmer_api, diagnosis):
        response = post(
            farmer_api, payload(diagnosis, was_correct=False, corrected_class_id=None, comment=None)
        )
        assert response.status_code == 201
        assert Feedback.objects.get().corrected_disease is None

    def test_several_feedback_items_on_one_diagnosis(self, farmer_api, diagnosis):
        """Append-only: the farmer says one thing, an officer later another. Both are kept."""
        post(farmer_api, payload(diagnosis))
        post(farmer_api, payload(diagnosis, was_correct=False, given_by_role="extension_officer"))
        assert Feedback.objects.filter(diagnosis=diagnosis).count() == 2

    def test_officer_answering_on_the_farmers_phone(self, farmer_api, farmer, diagnosis):
        post(farmer_api, payload(diagnosis, given_by_role="extension_officer"))
        feedback = Feedback.objects.get()
        assert feedback.given_by_role == "extension_officer"  # as reported
        assert feedback.given_by == farmer  # the account that sent it, so it can be told apart

    def test_extension_officer_account_can_review_any_diagnosis(self, diagnosis):
        officer = FarmerFactory(phone="+260961111111", role="extension_officer")
        response = post(signed_in(officer), payload(diagnosis))
        assert response.status_code == 201
        assert Feedback.objects.get().given_by_role == "extension_officer"


class TestIdempotency:
    def test_sending_twice_stores_once(self, farmer_api, diagnosis):
        body = payload(diagnosis)
        first, second = post(farmer_api, body), post(farmer_api, {**body, "was_correct": False})
        assert (first.status_code, second.status_code) == (201, 200)
        assert second.json() == first.json()
        assert Feedback.objects.get().was_correct is True  # the original, unchanged

    def test_duplicate_is_reported_even_if_the_resend_is_invalid(self, farmer_api, diagnosis):
        """Same rule as diagnosis sync: a stored item always leaves the phone's queue."""
        body = payload(diagnosis)
        post(farmer_api, body)
        resend = {**body, "was_correct": False, "corrected_class_id": "maize__alien_blight"}
        assert post(farmer_api, resend).status_code == 200

    def test_another_accounts_client_id_is_a_409(self, farmer_api, taxonomy):
        theirs = DiagnosisFactory(farmer=FarmerFactory(phone="+260961111111"))
        other_feedback = Feedback.objects.create(
            client_id=uuid.uuid4(),
            diagnosis=theirs,
            given_by=theirs.farmer,
            given_by_role="farmer",
            was_correct=True,
        )
        mine = DiagnosisFactory(farmer=FarmerFactory(phone="+260971234567"))
        response = post(farmer_api, payload(mine, client_id=str(other_feedback.client_id)))
        assert response.status_code == 409
        assert response.json()["code"] == "conflict"
        assert_matches_contract(response.json(), "Error")


class TestInvalid:
    @pytest.mark.parametrize(
        "overrides, field",
        [
            ({"client_id": "nope"}, "client_id"),
            ({"was_correct": "maybe"}, "was_correct"),
            ({"was_correct": True, "corrected_class_id": "maize__common_rust"}, "corrected_class_id"),
            ({"was_correct": False, "corrected_class_id": "maize__alien_blight"}, "corrected_class_id"),
            ({"comment": "x" * 501}, "comment"),
            ({"given_by_role": "agronomist"}, "given_by_role"),
            ({"diagnosis_client_id": str(uuid.uuid4())}, "diagnosis_client_id"),
        ],
    )
    def test_invalid_feedback_is_a_400_naming_the_field(self, farmer_api, diagnosis, overrides, field):
        body = {
            "client_id": str(uuid.uuid4()),
            "diagnosis_client_id": str(diagnosis.client_id),
            "was_correct": True,
        }
        response = post(farmer_api, {**body, **overrides})
        assert response.status_code == 400, response.json()
        assert_matches_contract(response.json(), "Error")
        assert field in response.json()["fields"], response.json()
        assert not Feedback.objects.exists()

    def test_a_farmer_cannot_give_feedback_on_someone_elses_diagnosis(self, farmer_api, taxonomy):
        theirs = DiagnosisFactory(farmer=FarmerFactory(phone="+260961111111"))
        response = post(farmer_api, payload(theirs))
        assert response.status_code == 400
        # Same message as "not synced", so it doesn't reveal that the diagnosis exists.
        assert "No synced diagnosis" in response.json()["fields"]["diagnosis_client_id"][0]

    def test_requires_a_token(self, diagnosis):
        assert APIClient().post(URL, payload(diagnosis), format="json").status_code == 401
