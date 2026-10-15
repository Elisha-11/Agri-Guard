import io
import json
import urllib.error
from datetime import timedelta
from unittest import mock

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.utils import timezone

from apps.accounts.models import OtpCode
from apps.accounts.sms import AfricasTalkingSmsBackend, ConsoleSmsBackend, SmsError


@pytest.fixture
def at_settings(settings):
    settings.AFRICASTALKING_USERNAME = "agriguard"
    settings.AFRICASTALKING_API_KEY = "test-key"
    settings.AFRICASTALKING_SENDER_ID = "AgriGuard"
    settings.AFRICASTALKING_SANDBOX = False
    return settings


def fake_response(payload):
    response = mock.MagicMock()
    response.__enter__.return_value.read.return_value = json.dumps(payload).encode()
    return response


SUCCESS = {
    "SMSMessageData": {
        "Message": "Sent to 1/1 Total Cost: ZMW 0.30",
        "Recipients": [{"statusCode": 101, "number": "+260971234567", "status": "Success", "messageId": "x"}],
    }
}


def test_africastalking_sends_the_expected_request(at_settings):
    with mock.patch("urllib.request.urlopen", return_value=fake_response(SUCCESS)) as urlopen:
        AfricasTalkingSmsBackend().send("+260971234567", "Your code is 123456")
    request = urlopen.call_args.args[0]
    assert request.full_url == AfricasTalkingSmsBackend.LIVE_URL
    assert request.get_header("Apikey") == "test-key"
    body = request.data.decode()
    assert "username=agriguard" in body and "to=%2B260971234567" in body and "from=AgriGuard" in body


def test_africastalking_sandbox_url(at_settings):
    at_settings.AFRICASTALKING_SANDBOX = True
    assert AfricasTalkingSmsBackend().url == AfricasTalkingSmsBackend.SANDBOX_URL


def test_africastalking_rejection_raises(at_settings):
    rejected = {"SMSMessageData": {"Message": "x", "Recipients": [{"status": "InvalidPhoneNumber"}]}}
    with mock.patch("urllib.request.urlopen", return_value=fake_response(rejected)):
        with pytest.raises(SmsError, match="InvalidPhoneNumber"):
            AfricasTalkingSmsBackend().send("+260971234567", "hi")


def test_africastalking_network_error_raises(at_settings):
    with mock.patch("urllib.request.urlopen", side_effect=urllib.error.URLError("no route")):
        with pytest.raises(SmsError):
            AfricasTalkingSmsBackend().send("+260971234567", "hi")


def test_africastalking_needs_credentials(settings):
    settings.AFRICASTALKING_USERNAME = ""
    settings.AFRICASTALKING_API_KEY = ""
    with pytest.raises(ImproperlyConfigured):
        AfricasTalkingSmsBackend()


def test_console_backend_prints_the_message(capsys):
    ConsoleSmsBackend().send("+260971234567", "Your code is 123456")
    assert "123456" in capsys.readouterr().out


@pytest.mark.django_db
def test_purge_deletes_only_old_codes():
    now = timezone.now()
    OtpCode.objects.create(phone="+260971234567", code_hash="a" * 64, expires_at=now)
    OtpCode.objects.create(
        phone="+260971234567", code_hash="b" * 64, created_at=now - timedelta(days=2), expires_at=now
    )
    out = io.StringIO()
    call_command("purge_otp_codes", stdout=out)
    assert OtpCode.objects.count() == 1
    assert "Deleted 1" in out.getvalue()
