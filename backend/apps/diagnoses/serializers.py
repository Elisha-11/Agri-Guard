"""Request bodies for `POST /diagnoses/sync/`. Names match the contract schemas.

The item serializers expect `context={"diseases": {class_id: Disease}, "farms": {client_id: Farm}}`, loaded
once per batch by apps/diagnoses/sync.py, so validating 25 items doesn't cost 25 lookups each.
"""

import uuid

from rest_framework import serializers

from apps.core.choices import Crop, PredictionStatus, Role, Severity
from apps.core.serializers import GeoPointField

MAX_BATCH = 25  # contract: items maxItems


class TopKItemSerializer(serializers.Serializer):
    class_id = serializers.CharField(max_length=64)
    confidence = serializers.FloatField(min_value=0, max_value=1)


class PredictionSerializer(serializers.Serializer):
    """Contract `Prediction`, built on the phone from the model output (docs/model-output.md §3)."""

    class_id = serializers.CharField(max_length=64)
    class_index = serializers.IntegerField(min_value=0)
    confidence = serializers.FloatField(min_value=0, max_value=1)
    status = serializers.ChoiceField(choices=PredictionStatus)
    severity = serializers.ChoiceField(choices=Severity)
    top_k = TopKItemSerializer(many=True, min_length=1, max_length=3)
    model_version = serializers.CharField(max_length=32)
    inference_ms = serializers.IntegerField(min_value=0, required=False, allow_null=True)

    def _known(self, class_id):
        return class_id in self.context["diseases"]

    def validate_class_id(self, value):
        if not self._known(value):
            raise serializers.ValidationError(
                f"Unknown class {value!r}. Is the backend's taxonomy up to date?"
            )
        return value

    def validate_top_k(self, value):
        unknown = [item["class_id"] for item in value if not self._known(item["class_id"])]
        if unknown:
            raise serializers.ValidationError(f"Unknown class(es): {', '.join(unknown)}.")
        return value


class DiagnosisItemSerializer(serializers.Serializer):
    """Contract `DiagnosisCreate`: one item of a sync batch."""

    client_id = serializers.UUIDField()
    farm_client_id = serializers.UUIDField(required=False, allow_null=True)
    crop = serializers.ChoiceField(choices=Crop)
    captured_at = serializers.DateTimeField()
    location = GeoPointField(allow_null=True)
    prediction = PredictionSerializer()
    app_version = serializers.CharField(max_length=20, required=False, allow_blank=True)

    def validate_farm_client_id(self, value):
        if value is not None and value not in self.context["farms"]:
            raise serializers.ValidationError(
                "No farm with this client_id on your account. Sync farms before diagnoses."
            )
        return value


class SyncBatchSerializer(serializers.Serializer):
    """The batch envelope. A malformed envelope is a 400; a bad item only fails that item (offline-sync.md).

    Every item must at least carry a UUID `client_id`, because each result is reported against it.
    """

    items = serializers.ListField(
        child=serializers.DictField(), min_length=1, max_length=MAX_BATCH, allow_empty=False
    )

    def validate_items(self, items):
        for position, item in enumerate(items):
            try:
                uuid.UUID(str(item.get("client_id")))
            except ValueError as exc:
                raise serializers.ValidationError(
                    f"Item {position} has no valid client_id (a UUID). Every item needs one."
                ) from exc
        return items


class SyncRequestSerializer(serializers.Serializer):
    """For the API docs only. Validation uses SyncBatchSerializer, then the item serializers one by one."""

    items = DiagnosisItemSerializer(many=True)


class SyncResultSerializer(serializers.Serializer):
    """Contract `SyncResult`. For the API docs; apps/diagnoses/sync.py builds the dicts."""

    client_id = serializers.UUIDField()
    status = serializers.ChoiceField(choices=["created", "duplicate", "conflict", "invalid"])
    id = serializers.UUIDField(allow_null=True, help_text="Server id, present for created and duplicate.")
    errors = serializers.DictField(
        child=serializers.ListField(child=serializers.CharField()),
        required=False,
        help_text="Only for invalid.",
    )


class SyncResponseSerializer(serializers.Serializer):
    results = SyncResultSerializer(many=True)


class FeedbackCreateSerializer(serializers.Serializer):
    """Contract `FeedbackCreate`: whether a synced diagnosis was right, and if not, what it really was."""

    client_id = serializers.UUIDField()
    diagnosis_client_id = serializers.UUIDField()
    was_correct = serializers.BooleanField()
    corrected_class_id = serializers.CharField(
        max_length=64, required=False, allow_null=True, allow_blank=True
    )
    comment = serializers.CharField(max_length=500, required=False, allow_null=True, allow_blank=True)
    given_by_role = serializers.ChoiceField(choices=Role, required=False)

    def validate(self, data):
        if data.get("was_correct") and data.get("corrected_class_id"):
            raise serializers.ValidationError(
                {"corrected_class_id": "Leave empty when the diagnosis was correct."}
            )
        return data


class FeedbackResultSerializer(serializers.Serializer):
    """Response of POST /feedback/ (201 created, 200 already stored)."""

    id = serializers.UUIDField()
    client_id = serializers.UUIDField()
