"""Sending SMS, behind a swappable backend chosen by the SMS_BACKEND setting (like Django's EMAIL_BACKEND).

- ConsoleSmsBackend: prints the message to the runserver console. Local development (the default).
- LocmemSmsBackend: keeps messages in `LocmemSmsBackend.outbox`. Tests.
- AfricasTalkingSmsBackend: sends real SMS through Africa's Talking. Staging and production.

See docs/backend/auth.md for how to configure each one.
"""

import json
import logging
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_string

logger = logging.getLogger(__name__)


class SmsError(Exception):
    """The provider didn't accept the message. The farmer won't receive a code."""


class BaseSmsBackend:
    def send(self, to: str, message: str) -> None:
        raise NotImplementedError


class ConsoleSmsBackend(BaseSmsBackend):
    """Prints the SMS so a developer can copy the code. Never use outside development: it exposes codes."""

    def send(self, to, message):
        print(f"\n[SMS to {to}] {message}\n", flush=True)


class LocmemSmsBackend(BaseSmsBackend):
    """Stores messages in memory for tests. Clear `outbox` between tests (the `sms_outbox` fixture does)."""

    outbox: list[dict] = []

    def send(self, to, message):
        self.outbox.append({"to": to, "message": message})


class AfricasTalkingSmsBackend(BaseSmsBackend):
    """Africa's Talking bulk SMS API (https://developers.africastalking.com/docs/sms/sending).

    Settings: AFRICASTALKING_USERNAME, AFRICASTALKING_API_KEY, optional AFRICASTALKING_SENDER_ID (a registered
    alphanumeric sender such as "AgriGuard"), and AFRICASTALKING_SANDBOX=True to use the free sandbox.
    """

    LIVE_URL = "https://api.africastalking.com/version1/messaging"
    SANDBOX_URL = "https://api.sandbox.africastalking.com/version1/messaging"
    TIMEOUT_SECONDS = 10

    def __init__(self):
        self.username = settings.AFRICASTALKING_USERNAME
        self.api_key = settings.AFRICASTALKING_API_KEY
        self.sender_id = settings.AFRICASTALKING_SENDER_ID
        self.url = self.SANDBOX_URL if settings.AFRICASTALKING_SANDBOX else self.LIVE_URL
        if not (self.username and self.api_key):
            raise ImproperlyConfigured("Set AFRICASTALKING_USERNAME and AFRICASTALKING_API_KEY to send SMS.")

    def send(self, to, message):
        fields = {"username": self.username, "to": to, "message": message}
        if self.sender_id:
            fields["from"] = self.sender_id
        request = urllib.request.Request(
            self.url,
            data=urllib.parse.urlencode(fields).encode(),
            headers={
                "apiKey": self.api_key,
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.TIMEOUT_SECONDS) as response:
                body = json.loads(response.read().decode())
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            # Log the number's last digits only; never the message, which contains the code.
            logger.error("SMS to ...%s failed: %s", to[-3:], exc)
            raise SmsError("SMS provider unreachable") from exc

        recipients = body.get("SMSMessageData", {}).get("Recipients", [])
        if not recipients or recipients[0].get("status") != "Success":
            status = (
                recipients[0].get("status") if recipients else body.get("SMSMessageData", {}).get("Message")
            )
            logger.error("SMS to ...%s rejected: %s", to[-3:], status)
            raise SmsError(f"SMS rejected: {status}")


def get_backend() -> BaseSmsBackend:
    return import_string(settings.SMS_BACKEND)()


def send_sms(to: str, message: str) -> None:
    get_backend().send(to, message)
