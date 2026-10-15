"""Contract `POST /diagnoses/sync/` (rules in apps/diagnoses/sync.py), `GET /diagnoses/` and
`POST /feedback/`.

See docs/offline-sync.md, docs/backend/diagnosis-sync.md and docs/backend/feedback.md.
"""

from django.db import IntegrityError, transaction
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import exceptions, serializers, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.catalog.models import Disease
from apps.core.choices import Role
from apps.core.serializers import ErrorSerializer, validate_model

from .models import Diagnosis, Feedback
from .pagination import HistoryPagination
from .serializers import (
    DiagnosisSerializer,
    FeedbackCreateSerializer,
    FeedbackResultSerializer,
    HistoryPageSerializer,
    SyncBatchSerializer,
    SyncRequestSerializer,
    SyncResponseSerializer,
)
from .sync import sync_diagnoses


class DiagnosisSyncView(APIView):
    @extend_schema(
        tags=["diagnoses"],
        operation_id="syncDiagnoses",
        summary="Upload a batch of diagnoses made offline (idempotent on client_id)",
        description="Always 200 with one result per item, in request order. See docs/offline-sync.md.",
        request=SyncRequestSerializer,
        responses={200: SyncResponseSerializer, 400: ErrorSerializer, 401: ErrorSerializer},
    )
    def post(self, request):
        batch = SyncBatchSerializer(data=request.data)
        batch.is_valid(raise_exception=True)
        return Response({"results": sync_diagnoses(request.user, batch.validated_data["items"])})


class HistoryQuerySerializer(serializers.Serializer):
    since = serializers.DateTimeField(required=False, help_text="Only diagnoses received after this time.")


class DiagnosisHistoryView(APIView):
    """Contract `GET /diagnoses/`: the farmer's own diagnoses, newest first, for restoring onto a new phone.

    `since` (a `received_at` the phone already has) gives only what arrived after it, so a phone can catch up
    cheaply. Follow `next` until it's null.
    """

    @extend_schema(
        tags=["diagnoses"],
        operation_id="listDiagnoses",
        summary="The farmer's diagnosis history (for restoring on a new device)",
        parameters=[
            OpenApiParameter("cursor", OpenApiTypes.STR, description="From the previous page's `next`."),
            OpenApiParameter(
                "since", OpenApiTypes.DATETIME, description="Only diagnoses received after this."
            ),
        ],
        responses={200: HistoryPageSerializer, 400: ErrorSerializer, 401: ErrorSerializer},
    )
    def get(self, request):
        query = HistoryQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        diagnoses = Diagnosis.objects.filter(farmer=request.user).select_related("farm")
        if "since" in query.validated_data:
            diagnoses = diagnoses.filter(received_at__gt=query.validated_data["since"])
        paginator = HistoryPagination()
        page = paginator.paginate_queryset(diagnoses, request, view=self)
        return paginator.get_paginated_response(DiagnosisSerializer(page, many=True).data)


class FeedbackClientIdConflict(exceptions.APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "This client_id is already used by another account. Generate a new UUID."
    default_code = "conflict"


def find_diagnosis(client_id, user):
    """The diagnosis this account may give feedback on: its own, or any one if the account is an officer.

    Anything else is reported as "not found", so the API never reveals another farmer's diagnoses.
    """
    diagnoses = Diagnosis.objects.select_related("disease")
    if user.role != Role.EXTENSION_OFFICER:
        diagnoses = diagnoses.filter(farmer=user)
    return diagnoses.filter(client_id=client_id).first()


class FeedbackView(APIView):
    """Contract `POST /feedback/`. Append-only and idempotent on `client_id` (docs/offline-sync.md).

    | `client_id`                        | Response        |
    |------------------------------------|-----------------|
    | new                                | 201             |
    | already sent by this account       | 200, unchanged  |
    | already used by another account    | 409 `conflict`  |
    """

    @extend_schema(
        tags=["feedback"],
        operation_id="submitFeedback",
        summary="Farmer or extension officer says whether a diagnosis was right (idempotent on client_id)",
        request=FeedbackCreateSerializer,
        responses={
            201: FeedbackResultSerializer,
            200: OpenApiResponse(FeedbackResultSerializer, description="Already stored (same client_id)"),
            400: ErrorSerializer,
            401: ErrorSerializer,
            409: OpenApiResponse(ErrorSerializer, description="client_id used by another account"),
        },
    )
    def post(self, request):
        serializer = FeedbackCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        existing = self._existing(data["client_id"], request.user)
        if existing:
            return Response(self._result(existing), status=status.HTTP_200_OK)

        diagnosis = find_diagnosis(data["diagnosis_client_id"], request.user)
        if diagnosis is None:
            raise ValidationError(
                {"diagnosis_client_id": ["No synced diagnosis with this client_id. Sync diagnoses first."]}
            )
        corrected = None
        if data.get("corrected_class_id"):
            corrected = Disease.objects.filter(class_id=data["corrected_class_id"]).first()
            if corrected is None:
                raise ValidationError(
                    {"corrected_class_id": [f"Unknown class {data['corrected_class_id']!r}."]}
                )

        feedback = Feedback(
            client_id=data["client_id"],
            diagnosis=diagnosis,
            given_by=request.user,
            # Self-reported: an officer may answer on the farmer's phone. given_by records the account.
            given_by_role=data.get("given_by_role") or request.user.role,
            was_correct=data["was_correct"],
            corrected_disease=corrected,
            comment=(data.get("comment") or "").strip(),
        )
        validate_model(
            feedback,
            exclude=["client_id"],
            field_names={"corrected_disease": "corrected_class_id", "diagnosis": "diagnosis_client_id"},
        )
        try:
            with transaction.atomic():
                feedback.save()
        except IntegrityError:
            existing = self._existing(data["client_id"], request.user)  # a parallel copy won the race
            if existing:
                return Response(self._result(existing), status=status.HTTP_200_OK)
            raise
        return Response(self._result(feedback), status=status.HTTP_201_CREATED)

    @staticmethod
    def _existing(client_id, user):
        feedback = Feedback.objects.filter(client_id=client_id).first()
        if feedback and feedback.given_by_id != user.pk:
            raise FeedbackClientIdConflict()
        return feedback

    @staticmethod
    def _result(feedback):
        return {"id": str(feedback.id), "client_id": str(feedback.client_id)}
