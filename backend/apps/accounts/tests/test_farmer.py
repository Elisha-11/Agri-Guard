import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from apps.accounts.models import Farmer

pytestmark = pytest.mark.django_db


def test_farmer_is_the_user_model():
    assert get_user_model() is Farmer


def test_farmer_signs_in_by_phone_and_has_no_password():
    farmer = Farmer.objects.create_user(phone="+260971234567")
    assert farmer.get_username() == "+260971234567"
    assert not farmer.has_usable_password()
    assert farmer.preferred_language == "en"
    assert farmer.role == "farmer"


def test_consent_is_off_by_default():
    farmer = Farmer.objects.create_user(phone="+260961234567")
    assert farmer.photo_consent is False
    assert farmer.location_consent is False


@pytest.mark.parametrize("phone", ["+260951234567", "+260961234567", "+260971234567", "+260751234567",
                                   "+260761234567", "+260771234567"])  # fmt: skip
def test_every_zambian_network_prefix_is_accepted(phone):
    Farmer.objects.create_user(phone=phone)


@pytest.mark.parametrize("phone", ["0971234567", "+26097123456", "+260981234567", "+27971234567", ""])
def test_bad_phone_numbers_are_rejected(phone):
    with pytest.raises((ValidationError, ValueError)):
        Farmer.objects.create_user(phone=phone)


def test_duplicate_phone_is_rejected():
    Farmer.objects.create_user(phone="+260971234567")
    with pytest.raises(ValidationError):
        Farmer.objects.create_user(phone="+260971234567")


def test_superuser_gets_a_password_for_the_admin():
    admin = Farmer.objects.create_superuser(phone="+260971111111", password="a-long-admin-pass")
    assert admin.is_staff and admin.is_superuser
    assert admin.check_password("a-long-admin-pass")


def test_str_prefers_display_name():
    assert str(Farmer(phone="+260971234567")) == "+260971234567"
    assert str(Farmer(phone="+260971234567", display_name="Mrs Banda")) == "Mrs Banda"
