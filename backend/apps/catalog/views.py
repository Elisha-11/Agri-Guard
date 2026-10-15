"""Contract `GET /advisory/bundle/`. The content rules are in apps/catalog/bundle.py."""

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.choices import Language
from apps.core.serializers import ErrorSerializer

from .bundle import build_bundle, etag_for


class BundleQuerySerializer(serializers.Serializer):
    lang = serializers.ChoiceField(choices=Language)


def etag_matches(header, etag):
    """True if an If-None-Match header lists `etag` (or is `*`). Weak and strong forms both match."""
    if not header:
        return False
    candidates = [tag.strip().removeprefix("W/") for tag in header.split(",")]
    return "*" in candidates or etag in candidates


class AdvisoryBundleView(APIView):
    """Public: the PWA downloads advice before the farmer signs in, so it works offline from first launch."""

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        tags=["advisory"],
        operation_id="getAdvisoryBundle",
        summary="All disease names and advice for one language, cached offline by the PWA",
        parameters=[
            OpenApiParameter("lang", OpenApiTypes.STR, enum=Language.values, required=True),
            OpenApiParameter("If-None-Match", OpenApiTypes.STR, OpenApiParameter.HEADER),
        ],
        responses={
            200: OpenApiResponse(description="Bundle (contract AdvisoryBundle)"),
            304: OpenApiResponse(description="Cached bundle is current"),
            400: ErrorSerializer,
        },
    )
    def get(self, request):
        query = BundleQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        bundle = build_bundle(query.validated_data["lang"])
        etag = etag_for(bundle)
        headers = {"ETag": etag, "Cache-Control": "no-cache"}  # always revalidate; a 304 is cheap
        if etag_matches(request.headers.get("If-None-Match"), etag):
            return Response(status=status.HTTP_304_NOT_MODIFIED, headers=headers)
        return Response(bundle, headers=headers)
