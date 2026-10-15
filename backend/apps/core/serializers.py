"""Serializer pieces shared by several apps."""

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from rest_framework.fields import empty

# Model fields whose errors the API reports under another name (the contract's field name).
API_FIELD_NAMES = {"latitude": "location", "longitude": "location"}


class GeoPointField(serializers.Field):
    """Contract `GeoPoint` {lat, lng} (or null) ⇄ a GeoPointMixin model's `latitude` / `longitude` columns.

    Use with `source="*"`. Coordinates are rounded to 3 decimal places here as well as on the phone, so a
    buggy or old client can never store a more precise location than ~110 m (docs/offline-sync.md, ADR 0004).
    Range checks are left to the model validators, which run in `validate_model`.
    """

    default_error_messages = {
        # Doubled braces: DRF formats these messages with str.format().
        "invalid": 'Expected {{"lat": number, "lng": number}} or null.',
    }

    def __init__(self, **kwargs):
        kwargs.setdefault("source", "*")
        kwargs.setdefault("required", False)
        super().__init__(**kwargs)

    def run_validation(self, data=empty):
        if data is None:  # explicit null clears the location
            return {"latitude": None, "longitude": None}
        return super().run_validation(data)

    def to_internal_value(self, data):
        if not isinstance(data, dict) or set(data) != {"lat", "lng"}:
            self.fail("invalid")
        try:
            lat, lng = (
                Decimal(str(data[k])).quantize(Decimal("0.001"), ROUND_HALF_UP) for k in ("lat", "lng")
            )
        except (InvalidOperation, TypeError, ValueError):
            self.fail("invalid")
        return {"latitude": lat, "longitude": lng}

    def to_representation(self, instance):
        return instance.location


class ErrorSerializer(serializers.Serializer):
    """Contract `Error`, produced by apps.core.exceptions.exception_handler. Used for the API docs."""

    code = serializers.CharField()
    message = serializers.CharField()
    fields = serializers.DictField(child=serializers.ListField(child=serializers.CharField()), required=False)


def validate_model(instance, exclude=None):
    """Run the model's `full_clean()` and re-raise its errors as a DRF 400 in the contract's Error shape.

    The database rules (docs/backend/data-model.md) then apply to API writes exactly as they do in the admin.
    """
    try:
        instance.full_clean(exclude=exclude)
    except DjangoValidationError as exc:
        fields = {}
        for name, messages in exc.message_dict.items():
            fields.setdefault(API_FIELD_NAMES.get(name, name), []).extend(messages)
        raise serializers.ValidationError(fields) from exc
