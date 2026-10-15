"""Contract `POST /diagnoses/sync/`. The rules are in apps/diagnoses/sync.py and docs/offline-sync.md."""

from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.serializers import ErrorSerializer

from .serializers import SyncBatchSerializer, SyncRequestSerializer, SyncResponseSerializer
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
