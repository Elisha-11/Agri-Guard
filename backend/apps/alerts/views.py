"""Contract `GET /alerts/nearby/` (ADR 0018)."""

from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.serializers import ErrorSerializer

from .outbreaks import nearby_alerts


class NearbyQuerySerializer(serializers.Serializer):
    """Query parameters; the same Zambia bounds as the contract's GeoPoint."""

    lat = serializers.FloatField(min_value=-18.1, max_value=-8.2)
    lng = serializers.FloatField(min_value=21.9, max_value=33.8)


class NearbyAlertsView(APIView):
    """Public, like the advisory bundle: farmers are warned before sign-in, and only aggregates leave."""

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        tags=["alerts"],
        operation_id="getNearbyAlerts",
        summary="Diseases reported by several farms near a location recently (aggregate counts only)",
        parameters=[
            OpenApiParameter("lat", float, required=True),
            OpenApiParameter("lng", float, required=True),
        ],
        responses={
            200: OpenApiResponse(description="Contract NearbyAlerts"),
            400: OpenApiResponse(ErrorSerializer, description="Missing or out-of-range coordinates"),
        },
    )
    def get(self, request):
        query = NearbyQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        data = nearby_alerts(query.validated_data["lat"], query.validated_data["lng"])
        # Counts change as diagnoses sync; the phone keeps its own offline copy.
        return Response(data, headers={"Cache-Control": "no-cache"})
