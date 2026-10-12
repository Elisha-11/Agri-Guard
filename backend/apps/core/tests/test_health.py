from django.conf import settings
from django.urls import reverse


def test_health_is_public_and_matches_contract(client):
    response = client.get(reverse("health"))

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": settings.APP_VERSION}


def test_openapi_schema_is_served(client):
    response = client.get(reverse("schema"))

    assert response.status_code == 200
