"""Contract `GET /farms/` and `POST /farms/`.

Farms are created on the phone, often offline, and the sync queue may send the same one more than once. So
creation is idempotent on `client_id` (docs/offline-sync.md):

| `client_id`                     | Response                         |
|---------------------------------|----------------------------------|
| new                             | 201 with the farm                |
| already used by this farmer     | 200 with the existing farm, unchanged |
| already used by another farmer  | 409 `conflict`                   |
"""

from django.db import IntegrityError, transaction
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.serializers import ErrorSerializer, validate_model

from .models import Farm
from .serializers import FarmSerializer


class ClientIdConflict(exceptions.APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "This client_id is already used by another account. Generate a new UUID."
    default_code = "conflict"


class FarmListView(APIView):
    @extend_schema(
        tags=["profile"],
        operation_id="listFarms",
        summary="Farms belonging to the current farmer",
        responses={200: FarmSerializer(many=True), 401: ErrorSerializer},
    )
    def get(self, request):
        return Response(FarmSerializer(request.user.farms.all(), many=True).data)

    @extend_schema(
        tags=["profile"],
        operation_id="createFarm",
        summary="Add a farm (idempotent on client_id)",
        request=FarmSerializer,
        responses={
            201: FarmSerializer,
            200: OpenApiResponse(FarmSerializer, description="Already created earlier (same client_id)"),
            400: ErrorSerializer,
            401: ErrorSerializer,
            409: OpenApiResponse(ErrorSerializer, description="client_id belongs to another farmer"),
        },
    )
    def post(self, request):
        serializer = FarmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        client_id = serializer.validated_data["client_id"]

        existing = self._existing(client_id, request.user)
        if existing:
            return Response(FarmSerializer(existing).data, status=status.HTTP_200_OK)

        farm = Farm(owner=request.user, **serializer.validated_data)
        validate_model(farm, exclude=["client_id"])
        try:
            with transaction.atomic():
                farm.save()
        except IntegrityError:
            # Two copies of the same request raced each other; the other one won.
            existing = self._existing(client_id, request.user)
            if existing:
                return Response(FarmSerializer(existing).data, status=status.HTTP_200_OK)
            raise
        return Response(FarmSerializer(farm).data, status=status.HTTP_201_CREATED)

    @staticmethod
    def _existing(client_id, owner):
        farm = Farm.objects.filter(client_id=client_id).first()
        if farm and farm.owner_id != owner.pk:
            raise ClientIdConflict()
        return farm
