from django.conf import settings
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthView(APIView):
    """Liveness check. Contract: GET /health/ -> {status, version}."""

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        responses=inline_serializer(
            "Health",
            {"status": serializers.ChoiceField(choices=["ok"]), "version": serializers.CharField()},
        )
    )
    def get(self, request):
        return Response({"status": "ok", "version": settings.APP_VERSION})
