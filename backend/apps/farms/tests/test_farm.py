from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from apps.core.tests.factories import FarmFactory

pytestmark = pytest.mark.django_db


def test_valid_farm_passes_validation():
    farm = FarmFactory.build(
        owner=FarmFactory().owner, latitude=Decimal("-15.417"), longitude=Decimal("28.283")
    )
    farm.full_clean()
    assert farm.location == {"lat": -15.417, "lng": 28.283}


@pytest.mark.parametrize("crops", [["rice"], ["maize", "maize"], "maize"])
def test_bad_crop_lists_are_rejected(crops):
    farm = FarmFactory.build(owner=FarmFactory().owner, crops=crops)
    with pytest.raises(ValidationError) as exc:
        farm.full_clean()
    assert "crops" in exc.value.message_dict


def test_location_outside_zambia_is_rejected():
    farm = FarmFactory.build(owner=FarmFactory().owner, latitude=Decimal("-25.0"), longitude=Decimal("28.0"))
    with pytest.raises(ValidationError) as exc:
        farm.full_clean()
    assert "latitude" in exc.value.message_dict


def test_half_a_location_is_rejected_by_the_database():
    with pytest.raises(IntegrityError):
        FarmFactory(latitude=Decimal("-15.4"), longitude=None)


def test_no_location_is_fine():
    assert FarmFactory().location is None


def test_client_id_is_unique():
    farm = FarmFactory()
    with pytest.raises(IntegrityError):
        FarmFactory(client_id=farm.client_id)
