"""Serializer pieces shared by several apps."""

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.fields import empty

# Model fields whose errors the API reports under another name (the contract's field name).
API_FIELD_NAMES = {"latitude": "location", "longitude": "location"}


@extend_schema_field(
    {
        "type": ["object", "null"],
        "required": ["lat", "lng"],
        "properties": {
            "lat": {"type": "number", "minimum": -18.1, "maximum": -8.2},
            "lng": {"type": "number", "minimum": 21.9, "maximum": 33.8},
        },
        "description": "Rounded to 3 decimal places (~110 m) by the server",
    }
)
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


def model_errors(instance, exclude=None, field_names=None, **full_clean_kwargs):
    """Run the model's `full_clean()`. Returns {api_field: [messages]}, or {} if valid.

    `field_names` maps model field names to the names the API uses (on top of API_FIELD_NAMES), e.g.
    {"disease": "prediction.class_id"}, so errors point at what the phone actually sent. Extra keyword
    arguments go to `full_clean()`, e.g. `validate_constraints=False` when the caller already guarantees
    them.
    """
    names = {**API_FIELD_NAMES, **(field_names or {})}
    try:
        instance.full_clean(exclude=exclude, **full_clean_kwargs)
    except DjangoValidationError as exc:
        fields = {}
        for name, messages in exc.message_dict.items():
            fields.setdefault(names.get(name, name), []).extend(messages)
        return fields
    return {}


def validate_model(instance, exclude=None, field_names=None):
    """Like `model_errors`, but raises a DRF 400 in the contract's Error shape.

    The database rules (docs/backend/data-model.md) then apply to API writes exactly as they do in the admin.
    """
    errors = model_errors(instance, exclude, field_names)
    if errors:
        raise serializers.ValidationError(errors)


def flatten_errors(detail, prefix=""):
    """Turn DRF's nested errors into {"dotted.path": [messages]}, e.g. "prediction.top_k.0.confidence".

    The contract's `SyncResult.errors` is a flat map of field to messages.
    """
    flat = {}
    if isinstance(detail, dict):
        for key, value in detail.items():
            # A nested serializer's own errors (e.g. "top_k must have 1-3 items") belong to the field itself.
            path = (
                prefix if key == "non_field_errors" and prefix else f"{prefix}.{key}" if prefix else str(key)
            )
            flat.update(flatten_errors(value, path))
    elif isinstance(detail, list) and any(isinstance(item, dict | list) for item in detail):
        for index, item in enumerate(detail):
            if item:
                flat.update(flatten_errors(item, f"{prefix}.{index}" if prefix else str(index)))
    else:
        messages = detail if isinstance(detail, list) else [detail]
        flat[prefix or "non_field_errors"] = [str(m) for m in messages]
    return flat
