"""Every admin page an agronomist or developer uses must at least load."""

import pytest
from django.urls import reverse

from apps.core.tests.factories import DiseaseAdviceFactory, FarmFactory, FeedbackFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin_client(client, django_user_model):
    admin = django_user_model.objects.create_superuser(phone="+260970000001", password="admin-pass-123")
    client.force_login(admin)
    return client


@pytest.fixture
def sample_data(taxonomy):
    FarmFactory()
    DiseaseAdviceFactory(disease=taxonomy["maize__grey_leaf_spot"])
    return FeedbackFactory().diagnosis


@pytest.mark.parametrize(
    "model",
    [
        "accounts_farmer",
        "farms_farm",
        "catalog_disease",
        "catalog_diseaseadvice",
        "diagnoses_diagnosis",
        "diagnoses_feedback",
    ],
)
def test_changelist_pages_load(admin_client, sample_data, model):
    assert admin_client.get(reverse(f"admin:{model}_changelist")).status_code == 200


def test_detail_pages_load(admin_client, sample_data):
    pages = [
        ("accounts_farmer", sample_data.farmer_id),
        ("diagnoses_diagnosis", sample_data.pk),
        ("catalog_disease", sample_data.disease_id),
    ]
    for model, pk in pages:
        assert admin_client.get(reverse(f"admin:{model}_change", args=[pk])).status_code == 200, model


def test_staff_can_add_a_farmer_through_the_admin(admin_client, django_user_model):
    response = admin_client.post(
        reverse("admin:accounts_farmer_add"),
        {"phone": "+260965555555", "password1": "x-long-pass-987", "password2": "x-long-pass-987",
         "usable_password": "true"},
    )  # fmt: skip
    assert response.status_code == 302, response.content[:2000]
    assert django_user_model.objects.filter(phone="+260965555555").exists()


def test_diseases_cannot_be_added_by_hand(admin_client):
    assert admin_client.get(reverse("admin:catalog_disease_add")).status_code == 403
