"""Request and response bodies for the auth endpoints. Names match the contract schemas."""

from rest_framework import serializers

from apps.core.validators import validate_zambian_phone


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


class ErrorSerializer(serializers.Serializer):
    """Contract `Error`, produced by apps.core.exceptions.exception_handler. Used for the API docs."""

    code = serializers.CharField()
    message = serializers.CharField()
    fields = serializers.DictField(child=serializers.ListField(child=serializers.CharField()), required=False)
