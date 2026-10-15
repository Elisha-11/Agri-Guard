"""The sign-in flow end to end, through the HTTP API, as the PWA will use it."""

import re
from datetime import timedelta
from unittest import mock

import pytest
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.accounts.models import Farmer, OtpCode
from apps.accounts.sms import SmsError
from apps.core.tests.contract import assert_matches_contract

pytestmark = pytest.mark.django_db

PHONE = "+260971234567"
REQUEST_URL = "/api/v1/auth/otp/request/"
VERIFY_URL = "/api/v1/auth/otp/verify/"
REFRESH_URL = "/api/v1/auth/token/refresh/"


@pytest.fixture
def api():
    return APIClient()


def request_code(api, outbox, phone=PHONE):
    response = api.post(REQUEST_URL, {"phone": phone}, format="json")
    assert response.status_code == 202, response.json()
    return re.search(r"\b(\d{6})\b", outbox[-1]["message"]).group(1)


def verify(api, code, phone=PHONE):
    return api.post(VERIFY_URL, {"phone": phone, "code": code}, format="json")


def wrong(code):
    return f"{(int(code) + 1) % 10**6:06d}"


def assert_error_shape(body, code):
    assert_matches_contract(body, "Error")
    assert body["code"] == code, body
    assert isinstance(body["message"], str) and body["message"]


class TestRequestCode:
    def test_sends_a_six_digit_code(self, api, sms_outbox):
        response = api.post(REQUEST_URL, {"phone": PHONE}, format="json")
        assert response.status_code == 202
        assert response.json() == {"expires_in": 600}
        assert len(sms_outbox) == 1
        assert sms_outbox[0]["to"] == PHONE
        assert re.search(r"\b\d{6}\b", sms_outbox[0]["message"])

    def test_code_is_stored_only_as_a_hash(self, api, sms_outbox):
        code = request_code(api, sms_outbox)
        stored = OtpCode.objects.get(phone=PHONE)
        assert code not in stored.code_hash
        assert len(stored.code_hash) == 64

    @pytest.mark.parametrize("phone", ["0971234567", "+260981234567", "", "+2609712345678"])
    def test_invalid_phone_is_a_400_in_the_contract_error_shape(self, api, sms_outbox, phone):
        response = api.post(REQUEST_URL, {"phone": phone}, format="json")
        assert response.status_code == 400
        body = response.json()
        assert "phone" in body["fields"]
        assert body["code"] in {"invalid_phone", "validation_error"}
        assert not sms_outbox

    def test_contract_example_error_code_for_a_bad_number(self, api, sms_outbox):
        response = api.post(REQUEST_URL, {"phone": "0971234567"}, format="json")
        assert_error_shape(response.json(), "invalid_phone")

    def test_fourth_request_in_15_minutes_is_rate_limited(self, api, sms_outbox):
        for _ in range(3):
            request_code(api, sms_outbox)
        response = api.post(REQUEST_URL, {"phone": PHONE}, format="json")
        assert response.status_code == 429
        assert_error_shape(response.json(), "rate_limited")
        assert 0 < int(response["Retry-After"]) <= 15 * 60
        assert len(sms_outbox) == 3

    def test_rate_limit_is_per_phone(self, api, sms_outbox):
        for _ in range(3):
            request_code(api, sms_outbox)
        request_code(api, sms_outbox, phone="+260961234567")

    def test_rate_limit_resets_after_the_window(self, api, sms_outbox):
        for _ in range(3):
            request_code(api, sms_outbox)
        OtpCode.objects.update(created_at=timezone.now() - timedelta(minutes=16))
        request_code(api, sms_outbox)

    def test_response_is_the_same_whether_or_not_the_account_exists(self, api, sms_outbox):
        Farmer.objects.create_user(phone="+260961234567")
        new = api.post(REQUEST_URL, {"phone": PHONE}, format="json")
        existing = api.post(REQUEST_URL, {"phone": "+260961234567"}, format="json")
        assert (new.status_code, new.json()) == (existing.status_code, existing.json())

    def test_blocked_account_gets_no_sms_but_the_same_response(self, api, sms_outbox):
        Farmer.objects.create_user(phone=PHONE, is_active=False)
        response = api.post(REQUEST_URL, {"phone": PHONE}, format="json")
        assert response.status_code == 202
        assert not sms_outbox

    def test_sms_provider_failure_is_a_503(self, api, sms_outbox):
        with mock.patch("apps.accounts.otp.send_sms", side_effect=SmsError("down")):
            response = api.post(REQUEST_URL, {"phone": PHONE}, format="json")
        assert response.status_code == 503
        assert_error_shape(response.json(), "sms_unavailable")

    def test_get_is_not_allowed(self, api):
        response = api.get(REQUEST_URL)
        assert response.status_code == 405
        assert_error_shape(response.json(), "method_not_allowed")


class TestVerifyCode:
    def test_first_sign_in_creates_the_farmer(self, api, sms_outbox):
        response = verify(api, request_code(api, sms_outbox))
        assert response.status_code == 200, response.json()
        body = response.json()
        assert_matches_contract(body, "TokenPair")
        assert set(body) == {"access", "refresh", "is_new_user"}
        assert body["is_new_user"] is True
        farmer = Farmer.objects.get(phone=PHONE)
        assert AccessToken(body["access"])["user_id"] == str(farmer.id)
        assert farmer.last_login is not None
        assert not farmer.has_usable_password()

    def test_returning_farmer_is_not_new(self, api, sms_outbox):
        Farmer.objects.create_user(phone=PHONE)
        response = verify(api, request_code(api, sms_outbox))
        assert response.json()["is_new_user"] is False
        assert Farmer.objects.count() == 1

    def test_wrong_code_is_a_401_and_counts_as_an_attempt(self, api, sms_outbox):
        code = request_code(api, sms_outbox)
        response = verify(api, wrong(code))
        assert response.status_code == 401
        assert_error_shape(response.json(), "invalid_code")
        assert OtpCode.objects.get().attempts == 1
        assert not Farmer.objects.exists()

    def test_after_five_wrong_codes_even_the_right_one_is_refused(self, api, sms_outbox):
        code = request_code(api, sms_outbox)
        for _ in range(5):
            assert verify(api, wrong(code)).status_code == 401
        response = verify(api, code)
        assert response.status_code == 429
        assert_error_shape(response.json(), "rate_limited")
        assert int(response["Retry-After"]) > 0

    def test_a_new_code_unlocks_sign_in(self, api, sms_outbox):
        code = request_code(api, sms_outbox)
        for _ in range(5):
            verify(api, wrong(code))
        assert verify(api, request_code(api, sms_outbox)).status_code == 200

    def test_code_works_only_once(self, api, sms_outbox):
        code = request_code(api, sms_outbox)
        assert verify(api, code).status_code == 200
        assert verify(api, code).status_code == 401

    def test_expired_code_is_refused(self, api, sms_outbox):
        code = request_code(api, sms_outbox)
        OtpCode.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
        assert verify(api, code).status_code == 401

    def test_requesting_a_new_code_cancels_the_old_one(self, api, sms_outbox):
        with mock.patch("apps.accounts.otp.generate_code", side_effect=["111111", "222222"]):
            request_code(api, sms_outbox)
            request_code(api, sms_outbox)
        assert verify(api, "111111").status_code == 401
        assert verify(api, "222222").status_code == 200

    def test_a_code_only_works_for_the_phone_it_was_sent_to(self, api, sms_outbox):
        other = "+260961234567"
        with mock.patch("apps.accounts.otp.generate_code", side_effect=["111111", "222222"]):
            request_code(api, sms_outbox)
            request_code(api, sms_outbox, phone=other)
        assert verify(api, "111111", phone=other).status_code == 401
        assert verify(api, "222222", phone=other).status_code == 200

    def test_no_code_ever_requested(self, api):
        assert verify(api, "123456").status_code == 401

    def test_blocked_account_cannot_sign_in(self, api, sms_outbox):
        farmer = Farmer.objects.create_user(phone=PHONE)
        code = request_code(api, sms_outbox)
        farmer.is_active = False
        farmer.save()
        assert verify(api, code).status_code == 401

    @pytest.mark.parametrize("code", ["12345", "1234567", "abcdef", ""])
    def test_malformed_code_is_a_400(self, api, code):
        response = verify(api, code)
        assert response.status_code == 400
        assert "code" in response.json()["fields"]


class TestRefresh:
    def sign_in(self, api, outbox):
        return verify(api, request_code(api, outbox)).json()

    def test_refresh_gives_a_new_pair(self, api, sms_outbox):
        tokens = self.sign_in(api, sms_outbox)
        response = api.post(REFRESH_URL, {"refresh": tokens["refresh"]}, format="json")
        assert response.status_code == 200
        body = response.json()
        assert set(body) == {"access", "refresh"}
        assert body["refresh"] != tokens["refresh"]

    def test_a_refresh_token_works_only_once(self, api, sms_outbox):
        tokens = self.sign_in(api, sms_outbox)
        api.post(REFRESH_URL, {"refresh": tokens["refresh"]}, format="json")
        response = api.post(REFRESH_URL, {"refresh": tokens["refresh"]}, format="json")
        assert response.status_code == 401
        assert_error_shape(response.json(), "token_not_valid")

    def test_garbage_token_is_a_401(self, api):
        response = api.post(REFRESH_URL, {"refresh": "not-a-token"}, format="json")
        assert response.status_code == 401
        assert_error_shape(response.json(), "token_not_valid")
