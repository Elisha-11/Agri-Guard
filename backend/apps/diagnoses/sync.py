"""Storing a batch of diagnoses sent by a phone. The rules are in docs/offline-sync.md:

| Situation                                  | Result `status` |
|--------------------------------------------|-----------------|
| new client_id, valid                       | created         |
| client_id already stored for this farmer   | duplicate (the stored copy is kept as is) |
| client_id already stored for another farmer| conflict        |
| fails validation                           | invalid + errors|

Items are processed in order, each in its own savepoint, so one bad item never loses the others. A client_id
repeated inside one batch is created once and reported as duplicate the second time.
"""

import logging
import uuid

from django.db import IntegrityError, transaction

from apps.catalog.models import Disease
from apps.core.serializers import flatten_errors, model_errors

from .models import Diagnosis
from .serializers import DiagnosisItemSerializer

logger = logging.getLogger(__name__)

# Model field -> the field the phone sent, so `errors` point at the payload (docs/backend/diagnosis-sync.md).
API_FIELD_NAMES = {
    "disease": "prediction.class_id",
    "class_index": "prediction.class_index",
    "confidence": "prediction.confidence",
    "status": "prediction.status",
    "severity": "prediction.severity",
    "top_k": "prediction.top_k",
    "model_version": "prediction.model_version",
    "inference_ms": "prediction.inference_ms",
    "farm": "farm_client_id",
}


def result(client_id, status, diagnosis_id=None, errors=None):
    """Contract `SyncResult`."""
    body = {"client_id": str(client_id), "status": status, "id": str(diagnosis_id) if diagnosis_id else None}
    if errors:
        body["errors"] = errors
    return body


def existing_result(diagnosis, farmer):
    if diagnosis.farmer_id == farmer.pk:
        return result(diagnosis.client_id, "duplicate", diagnosis.id)
    # Another account already used this UUID: a client bug or a cloned device. Never reveal their record.
    logger.warning("Diagnosis client_id %s conflict: sent by farmer %s", diagnosis.client_id, farmer.pk)
    return result(diagnosis.client_id, "conflict")


def build_diagnosis(farmer, data, diseases, farms):
    prediction = data["prediction"]
    farm = farms.get(data.get("farm_client_id"))
    diagnosis = Diagnosis(
        client_id=data["client_id"],
        farmer=farmer,
        farm=farm,
        crop=data["crop"],
        captured_at=data["captured_at"],
        app_version=data.get("app_version", ""),
        disease=diseases[prediction["class_id"]],
        class_index=prediction["class_index"],
        confidence=prediction["confidence"],
        status=prediction["status"],
        severity=prediction["severity"],
        top_k=[dict(item) for item in prediction["top_k"]],
        model_version=prediction["model_version"],
        inference_ms=prediction.get("inference_ms"),
    )
    # Location is kept only with the farmer's consent (docs/backend/diagnosis-sync.md, "Location").
    if farmer.location_consent:
        diagnosis.latitude = data.get("latitude")
        diagnosis.longitude = data.get("longitude")
    return diagnosis


def sync_one(farmer, raw, diseases, farms, known):
    """Process one item. `known` maps client_id -> Diagnosis already stored (updated as items are created)."""
    client_id = uuid.UUID(str(raw["client_id"]))
    if client_id in known:
        return existing_result(known[client_id], farmer)

    serializer = DiagnosisItemSerializer(data=raw, context={"diseases": diseases, "farms": farms})
    if not serializer.is_valid():
        return result(client_id, "invalid", errors=flatten_errors(serializer.errors))

    diagnosis = build_diagnosis(farmer, serializer.validated_data, diseases, farms)
    # Only the model's field validators and clean() (crop/class/severity/top_k rules) are needed here. The
    # related rows were just loaded, and uniqueness and check constraints are enforced by the database on
    # insert. Re-checking them would cost ~9 extra queries per item.
    errors = model_errors(
        diagnosis,
        exclude=["id", "client_id", "farmer", "disease", "farm"],
        field_names=API_FIELD_NAMES,
        validate_unique=False,
        validate_constraints=False,
    )
    if errors:
        return result(client_id, "invalid", errors=errors)

    try:
        with transaction.atomic():
            diagnosis.save()
    except IntegrityError:
        # The same item arrived in a parallel request (e.g. two tabs flushing at once) and won the race.
        stored = Diagnosis.objects.filter(client_id=client_id).first()
        if stored is None:
            raise
        known[client_id] = stored
        return existing_result(stored, farmer)

    known[client_id] = diagnosis
    return result(client_id, "created", diagnosis.id)


def sync_diagnoses(farmer, items):
    """Store a batch of up to 25 diagnoses for `farmer`. Returns one SyncResult per item, in request order."""
    client_ids = [uuid.UUID(str(item["client_id"])) for item in items]
    known = {
        d.client_id: d
        for d in Diagnosis.objects.filter(client_id__in=client_ids).only("id", "client_id", "farmer")
    }
    diseases = {d.class_id: d for d in Disease.objects.all()}
    farms = {f.client_id: f for f in farmer.farms.all()}
    return [sync_one(farmer, raw, diseases, farms, known) for raw in items]
