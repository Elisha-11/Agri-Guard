"""Contract `GET /model/latest/`."""

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import exceptions, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.serializers import ErrorSerializer

from .models import ModelRelease


class NoModelReleased(exceptions.APIException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = "No model has been released yet."
    default_code = "no_model"


class LatestModelView(APIView):
    """Public: the PWA checks for a new model whenever it's online, signed in or not."""

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        tags=["model"],
        operation_id="getLatestModel",
        summary="Which model the PWA should be running",
        responses={
            200: OpenApiResponse(description="Current model manifest (contract ModelManifest)"),
            404: OpenApiResponse(ErrorSerializer, description="No model released yet (`no_model`)"),
        },
    )
    def get(self, request):
        release = ModelRelease.objects.filter(is_current=True).first()
        if release is None:
            raise NoModelReleased()
        # Small, and must never be stale after a rollback: always revalidate.
        return Response(release.manifest(), headers={"Cache-Control": "no-cache"})
