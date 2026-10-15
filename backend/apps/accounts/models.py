"""The Farmer account (the project's user model, ADR 0003) and SMS sign-in codes (ADR 0006)."""

import uuid

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone

from apps.core.choices import Language, Role
from apps.core.validators import validate_zambian_phone


class FarmerManager(BaseUserManager):
    """Creates accounts keyed on phone number.

    Farmers sign in with an SMS code, so they get no usable password. Staff who use the Django admin get
    a password.
    """

    use_in_migrations = True

    def create_user(self, phone, password=None, **extra_fields):
        if not phone:
            raise ValueError("A phone number is required.")
        user = self.model(phone=phone, **extra_fields)
        user.full_clean(exclude=["password"])
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, phone, password, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if not (extra_fields["is_staff"] and extra_fields["is_superuser"]):
            raise ValueError("A superuser must have is_staff=True and is_superuser=True.")
        return self.create_user(phone, password, **extra_fields)


class Farmer(AbstractBaseUser, PermissionsMixin):
    """A farmer or extension officer. Contract schema `Farmer`."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    phone = models.CharField(
        max_length=13,
        unique=True,
        validators=[validate_zambian_phone],
        help_text="Zambian mobile in E.164, e.g. +260971234567. This is the login; there is no email.",
    )
    display_name = models.CharField(max_length=80, blank=True, help_text="Optional name shown in the app.")
    preferred_language = models.CharField(
        max_length=3,
        choices=Language,
        default=Language.ENGLISH,
        help_text="Language for advice, UI text and voice narration.",
    )
    province = models.CharField(
        max_length=40, blank=True, help_text="Optional, for district-level reporting."
    )
    district = models.CharField(
        max_length=60, blank=True, help_text="Optional, for district-level reporting."
    )
    role = models.CharField(
        max_length=20,
        choices=Role,
        default=Role.FARMER,
        help_text="Extension officers' feedback is weighted more heavily when reviewing diagnoses.",
    )
    photo_consent = models.BooleanField(
        default=False,
        help_text="Farmer agreed that uploaded leaf photos may be used to improve the model. Off by default.",
    )
    location_consent = models.BooleanField(
        default=False, help_text="Farmer agreed to attach (rounded) GPS to diagnoses. Off by default."
    )
    updated_at = models.DateTimeField(
        default=timezone.now,
        help_text=(
            "Client timestamp of the last profile edit, used for last-write-wins (docs/offline-sync.md). "
            "Set by the API, not automatically, so an older offline edit can't overwrite a newer one."
        ),
    )

    is_active = models.BooleanField(default=True, help_text="Untick to block sign-in without deleting data.")
    is_staff = models.BooleanField(default=False, help_text="Can sign in to the Django admin.")
    date_joined = models.DateTimeField(default=timezone.now, editable=False)

    objects = FarmerManager()

    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = "farmer"
        ordering = ["-date_joined"]

    def __str__(self):
        return self.display_name or self.phone


class OtpCode(models.Model):
    """A one-time sign-in code sent by SMS. Contract `/auth/otp/request/` and `/auth/otp/verify/`.

    Only a keyed hash of the code is stored, so neither a database leak nor an admin can read live codes.
    Not linked to Farmer, because the first code is sent before the account exists. See apps/accounts/otp.py.
    """

    phone = models.CharField(max_length=13, validators=[validate_zambian_phone], db_index=True)
    code_hash = models.CharField(
        max_length=64, help_text="HMAC-SHA256 of phone and code, keyed by SECRET_KEY."
    )
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    expires_at = models.DateTimeField(help_text="Set to now when a newer code is requested.")
    attempts = models.PositiveSmallIntegerField(default=0, help_text="Wrong guesses so far.")
    used_at = models.DateTimeField(null=True, blank=True, help_text="When it was successfully used.")

    class Meta:
        verbose_name = "SMS sign-in code"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.phone} @ {self.created_at:%Y-%m-%d %H:%M}"
