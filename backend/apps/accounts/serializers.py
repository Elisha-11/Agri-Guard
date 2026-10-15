"""Request and response bodies for the auth endpoints. Names match the contract schemas."""

from rest_framework import serializers

from apps.core.choices import Language
from apps.core.validators import validate_zambian_phone

from .models import Farmer


class OtpRequestSerializer(serializers.Serializer):
    """Contract `OtpRequest`."""

    phone = serializers.CharField(max_length=13, validators=[validate_zambian_phone])


class OtpRequestResponseSerializer(serializers.Serializer):
    expires_in = serializers.IntegerField(help_text="Seconds until the code expires.")


class OtpVerifySerializer(serializers.Serializer):
    """Contract `OtpVerify`."""

    phone = serializers.CharField(max_length=13, validators=[validate_zambian_phone])
    code = serializers.RegexField(
        r"^\d{6}$", max_length=6, error_messages={"invalid": "The code is 6 digits."}
    )


class TokenPairSerializer(serializers.Serializer):
    """Contract `TokenPair`."""

    access = serializers.CharField()
    refresh = serializers.CharField()
    is_new_user = serializers.BooleanField(help_text="True on first sign-in, so the PWA shows onboarding.")


class RefreshedTokensSerializer(serializers.Serializer):
    """Response of `/auth/token/refresh/`. The refresh token rotates, so store the new one."""

    access = serializers.CharField()
    refresh = serializers.CharField()


class NullableBlankCharField(serializers.CharField):
    """Contract `string | null` stored as "" in the database (Django's convention for text fields)."""

    def __init__(self, **kwargs):
        kwargs.setdefault("allow_null", True)
        kwargs.setdefault("allow_blank", True)
        kwargs.setdefault("required", False)
        super().__init__(**kwargs)

    def validate_empty_values(self, data):
        if data is None:
            return True, ""
        return super().validate_empty_values(data)

    def to_representation(self, value):
        return value or None


class FarmerSerializer(serializers.ModelSerializer):
    """Contract `Farmer` (GET/PATCH /me/ response)."""

    display_name = NullableBlankCharField(max_length=80)
    province = NullableBlankCharField(max_length=40)
    district = NullableBlankCharField(max_length=60)

    class Meta:
        model = Farmer
        fields = [
            "id",
            "phone",
            "display_name",
            "preferred_language",
            "province",
            "district",
            "role",
            "photo_consent",
            "location_consent",
            "updated_at",
        ]
        read_only_fields = fields


class FarmerUpdateSerializer(serializers.Serializer):
    """Contract `FarmerUpdate`. Phone and role can't be changed here."""

    display_name = NullableBlankCharField(max_length=80)
    preferred_language = serializers.ChoiceField(choices=Language, required=False)
    province = NullableBlankCharField(max_length=40)
    district = NullableBlankCharField(max_length=60)
    photo_consent = serializers.BooleanField(required=False)
    location_consent = serializers.BooleanField(required=False)
    updated_at = serializers.DateTimeField(
        required=False, help_text="When the edit was made on the phone. Omit to mean 'now'."
    )
