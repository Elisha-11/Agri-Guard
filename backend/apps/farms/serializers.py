from rest_framework import serializers

from apps.core.choices import Crop
from apps.core.serializers import GeoPointField

from .models import Farm


class FarmSerializer(serializers.ModelSerializer):
    """Contract `FarmCreate` (request) and `Farm` (response)."""

    crops = serializers.ListField(child=serializers.ChoiceField(choices=Crop), required=False)
    size_hectares = serializers.DecimalField(
        max_digits=8, decimal_places=2, min_value=0, allow_null=True, required=False, coerce_to_string=False
    )
    location = GeoPointField(allow_null=True)

    class Meta:
        model = Farm
        fields = ["id", "client_id", "name", "crops", "size_hectares", "location"]
        read_only_fields = ["id"]
        # client_id's uniqueness is handled by the view (duplicates are idempotent, not errors).
        extra_kwargs = {"client_id": {"validators": []}}
