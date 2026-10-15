import os

import pytest

# Tests never need a real secret; CI and local runs both work without a .env file.
os.environ.setdefault("SECRET_KEY", "test-only-not-secret")


@pytest.fixture
def taxonomy(db):
    """The real 19 classes from ml/labels.json, loaded the same way production loads them."""
    from django.core.management import call_command

    from apps.catalog.models import Disease

    call_command("load_taxonomy", verbosity=0)
    return {d.class_id: d for d in Disease.objects.all()}
