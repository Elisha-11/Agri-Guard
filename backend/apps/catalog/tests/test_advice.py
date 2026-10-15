from datetime import date

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from apps.core.tests.factories import DiseaseAdviceFactory, DiseaseFactory

pytestmark = pytest.mark.django_db


def test_valid_advice_passes_validation():
    DiseaseAdviceFactory.build(disease=DiseaseFactory()).full_clean()


def test_cannot_publish_without_an_agronomist_review():
    advice = DiseaseAdviceFactory.build(disease=DiseaseFactory(), is_published=True)
    with pytest.raises(ValidationError) as exc:
        advice.full_clean()
    assert "is_published" in exc.value.message_dict


def test_database_also_blocks_unreviewed_publishing():
    with pytest.raises(IntegrityError):
        DiseaseAdviceFactory(is_published=True)


def test_reviewed_advice_can_be_published():
    advice = DiseaseAdviceFactory(
        is_published=True, reviewed_by="Dr. Agronomist, ZARI", reviewed_at=date(2026, 10, 20)
    )
    assert advice.is_published


def test_chemical_treatment_needs_a_safety_warning():
    advice = DiseaseAdviceFactory.build(disease=DiseaseFactory(), involves_chemicals=True)
    with pytest.raises(ValidationError) as exc:
        advice.full_clean()
    assert "safety_warning" in exc.value.message_dict
    with pytest.raises(IntegrityError):
        advice.save()


def test_one_advice_row_per_language():
    advice = DiseaseAdviceFactory()
    DiseaseAdviceFactory(disease=advice.disease, lang="ny")
    with pytest.raises(IntegrityError):
        DiseaseAdviceFactory(disease=advice.disease, lang="en")


@pytest.mark.parametrize(
    "section",
    [
        {"title": "", "steps": [], "audio_url": None},
        {"title": "Now", "steps": "spray"},
        {"title": "Now", "steps": ["ok", ""]},
        {"title": "Now", "steps": [], "colour": "red"},
        ["Remove leaves"],
    ],
)
def test_malformed_advice_sections_are_rejected(section):
    advice = DiseaseAdviceFactory.build(disease=DiseaseFactory(), treatment=section)
    with pytest.raises(ValidationError) as exc:
        advice.full_clean()
    assert "treatment" in exc.value.message_dict


def test_disease_class_id_must_match_crop():
    disease = DiseaseFactory.build(class_id="maize__rust", crop="soybean", class_index=40)
    with pytest.raises(ValidationError) as exc:
        disease.full_clean()
    assert "class_id" in exc.value.message_dict


def test_only_healthy_class_ids_can_be_healthy():
    disease = DiseaseFactory.build(class_id="maize__rust", class_index=40, is_healthy=True)
    with pytest.raises(ValidationError) as exc:
        disease.full_clean()
    assert "is_healthy" in exc.value.message_dict
