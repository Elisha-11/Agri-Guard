"""Phone sign-in with one-time SMS codes. The rules (docs/backend/auth.md, ADR 0006):

- A code is 6 random digits, valid for OTP_TTL_SECONDS (10 minutes). Requesting a new one cancels the old one.
- At most OTP_MAX_REQUESTS (3) codes per phone per OTP_REQUEST_WINDOW_SECONDS (15 minutes).
- At most OTP_MAX_ATTEMPTS (5) wrong guesses per code; after that it's locked until it expires.
  Together with the request limit, that caps guessing at 15 tries per 15 minutes per phone.
- Requesting a code never reveals whether an account exists, and inactive accounts get no SMS.
- A correct code creates the Farmer on first sign-in.

Views stay thin and call `request_code` / `verify_code`; these raise the exceptions below.
"""

import hashlib
import hmac
import math
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import update_last_login
from django.db import transaction
from django.utils import timezone

from .models import Farmer, OtpCode
from .sms import send_sms


class OtpRateLimited(Exception):
    """Too many codes requested, or too many wrong guesses. `wait` is seconds until a retry is allowed."""

    def __init__(self, wait: int):
        super().__init__(wait)
        self.wait = max(1, wait)


class OtpInvalid(Exception):
    """Wrong, expired, already used, or never sent. Deliberately one error so callers can't tell which."""


def hash_code(phone: str, code: str) -> str:
    key = settings.SECRET_KEY.encode()
    return hmac.new(key, f"{phone}:{code}".encode(), hashlib.sha256).hexdigest()


def generate_code() -> str:
    return f"{secrets.randbelow(10**6):06d}"


def sms_text(code: str) -> str:
    # English only for now: Nyanja, Bemba and Tonga need native-speaker translations (docs/backend/auth.md).
    minutes = settings.OTP_TTL_SECONDS // 60
    return (
        f"Your AgriGuard code is {code}. It expires in {minutes} minutes. Never share this code with anyone."
    )


def _seconds_until(moment) -> int:
    return math.ceil((moment - timezone.now()).total_seconds())


def request_code(phone: str) -> int:
    """Send a new code to `phone`. Returns seconds until it expires. Raises OtpRateLimited or sms.SmsError."""
    now = timezone.now()
    window_start = now - timedelta(seconds=settings.OTP_REQUEST_WINDOW_SECONDS)
    recent = OtpCode.objects.filter(phone=phone, created_at__gte=window_start).order_by("created_at")
    if recent.count() >= settings.OTP_MAX_REQUESTS:
        oldest = recent.first()
        raise OtpRateLimited(
            _seconds_until(oldest.created_at + timedelta(seconds=settings.OTP_REQUEST_WINDOW_SECONDS))
        )

    code = generate_code()
    with transaction.atomic():
        OtpCode.objects.filter(phone=phone, used_at__isnull=True, expires_at__gt=now).update(expires_at=now)
        OtpCode.objects.create(
            phone=phone,
            code_hash=hash_code(phone, code),
            created_at=now,
            expires_at=now + timedelta(seconds=settings.OTP_TTL_SECONDS),
        )

    blocked = Farmer.objects.filter(phone=phone, is_active=False).exists()
    if not blocked:
        send_sms(phone, sms_text(code))
    return settings.OTP_TTL_SECONDS


def verify_code(phone: str, code: str) -> tuple[Farmer, bool]:
    """Check `code` for `phone`. Returns (farmer, created). Raises OtpInvalid or OtpRateLimited."""
    now = timezone.now()
    outcome = None
    with transaction.atomic():
        otp = (
            OtpCode.objects.select_for_update()
            .filter(phone=phone, used_at__isnull=True, expires_at__gt=now)
            .order_by("-created_at")
            .first()
        )
        if otp is None:
            outcome = "invalid"
        elif otp.attempts >= settings.OTP_MAX_ATTEMPTS:
            outcome = "locked"
        elif not hmac.compare_digest(otp.code_hash, hash_code(phone, code)):
            # Saved before raising (outside this block) so the wrong guess is counted.
            otp.attempts += 1
            otp.save(update_fields=["attempts"])
            outcome = "invalid"
        else:
            otp.used_at = now
            otp.save(update_fields=["used_at"])
            farmer = Farmer.objects.filter(phone=phone).first()
            created = farmer is None
            if created:
                farmer = Farmer.objects.create_user(phone=phone)
            if not farmer.is_active:
                outcome = "invalid"
            else:
                update_last_login(None, farmer)
                return farmer, created

    if outcome == "locked":
        raise OtpRateLimited(_seconds_until(otp.expires_at))
    raise OtpInvalid()
