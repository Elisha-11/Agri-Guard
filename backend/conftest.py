import os

import pytest

# Tests never need a real secret; CI and local runs both work without a .env file.
# At least 32 bytes: SECRET_KEY also signs the JWTs (HS256).
os.environ.setdefault("SECRET_KEY", "test-only-not-secret-but-long-enough-for-hs256")


@pytest.fixture
def taxonomy(db):
    """The real 19 classes from ml/labels.json, loaded the same way production loads them."""
    from django.core.management import call_command

    from apps.catalog.models import Disease

    call_command("load_taxonomy", verbosity=0)
    return {d.class_id: d for d in Disease.objects.all()}


@pytest.fixture
def sms_outbox():
    """SMS "sent" during the test (test settings use LocmemSmsBackend). Starts empty."""
    from apps.accounts.sms import LocmemSmsBackend

    LocmemSmsBackend.outbox.clear()
    yield LocmemSmsBackend.outbox
    LocmemSmsBackend.outbox.clear()


@pytest.fixture
def farmer(db):
    from apps.core.tests.factories import FarmerFactory

    return FarmerFactory(phone="+260971234567")


@pytest.fixture
def farmer_api(farmer):
    """An API client signed in as `farmer` with a real JWT, exactly as the PWA sends it."""
    from rest_framework.test import APIClient
    from rest_framework_simplejwt.tokens import RefreshToken

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(farmer).access_token}")
    return client
