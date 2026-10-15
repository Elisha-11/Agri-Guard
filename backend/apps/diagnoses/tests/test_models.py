from datetime import UTC, datetime, timedelta

import pytest
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import IntegrityError
from django.db.models.deletion import ProtectedError

from apps.core.tests.factories import DiagnosisFactory, FarmerFactory, FarmFactory, FeedbackFactory

pytestmark = pytest.mark.django_db


def errors_for(diagnosis):
    with pytest.raises(ValidationError) as exc:
        diagnosis.full_clean()
    return exc.value.message_dict


def test_factory_diagnosis_is_valid(taxonomy):
    DiagnosisFactory.build(farmer=FarmerFactory()).full_clean()


def test_same_client_id_never_creates_two_rows(taxonomy):
    diagnosis = DiagnosisFactory()
    with pytest.raises(IntegrityError):
        DiagnosisFactory(client_id=diagnosis.client_id)


def test_disease_must_belong_to_the_crop(taxonomy):
    diagnosis = DiagnosisFactory.build(farmer=FarmerFactory(), crop="cassava")
    assert "disease" in errors_for(diagnosis)


def test_class_index_must_match_the_disease(taxonomy):
    diagnosis = DiagnosisFactory.build(farmer=FarmerFactory(), class_index=7)
    assert "class_index" in errors_for(diagnosis)


def test_healthy_leaf_has_severity_none(taxonomy):
    healthy = dict(
        farmer=FarmerFactory(),
        disease=taxonomy["maize__healthy"],
        class_index=0,
        top_k=[{"class_id": "maize__healthy", "confidence": 0.95}],
    )
    assert "severity" in errors_for(DiagnosisFactory.build(**healthy, severity="moderate"))
    DiagnosisFactory.build(**healthy, severity="none").full_clean()


def test_disease_cannot_have_severity_none(taxonomy):
    assert "severity" in errors_for(DiagnosisFactory.build(farmer=FarmerFactory(), severity="none"))


@pytest.mark.parametrize(
    "top_k",
    [
        [],
        [
            {"class_id": "maize__grey_leaf_spot", "confidence": 0.5},
            {"class_id": "maize__healthy", "confidence": 0.6},
        ],
        [{"class_id": "maize__grey_leaf_spot", "confidence": 1.5}],
        [{"class_id": "maize__grey_leaf_spot"}],
        [{"class_id": "maize__northern_leaf_blight", "confidence": 0.91}],
    ],
)
def test_malformed_top_k_is_rejected(taxonomy, top_k):
    assert "top_k" in errors_for(DiagnosisFactory.build(farmer=FarmerFactory(), top_k=top_k))


def test_confidence_must_be_a_probability(taxonomy):
    assert "confidence" in errors_for(DiagnosisFactory.build(farmer=FarmerFactory(), confidence=1.2))
    with pytest.raises(IntegrityError):
        DiagnosisFactory(confidence=1.2)


def test_farm_must_belong_to_the_same_farmer(taxonomy):
    someone_elses_farm = FarmFactory()
    assert "farm" in errors_for(DiagnosisFactory.build(farmer=FarmerFactory(), farm=someone_elses_farm))


def test_a_disease_with_diagnoses_cannot_be_deleted(taxonomy):
    DiagnosisFactory()
    with pytest.raises(ProtectedError):
        taxonomy["maize__grey_leaf_spot"].delete()


def test_deleting_a_farm_keeps_its_diagnoses(taxonomy):
    farm = FarmFactory()
    diagnosis = DiagnosisFactory(farmer=farm.owner, farm=farm)
    farm.delete()
    diagnosis.refresh_from_db()
    assert diagnosis.farm is None


class TestReportedAt:
    """docs/offline-sync.md, Clock skew."""

    def test_uses_device_time_normally(self, taxonomy):
        diagnosis = DiagnosisFactory()
        assert diagnosis.reported_at == diagnosis.captured_at

    def test_uses_server_time_when_device_clock_is_before_2026(self, taxonomy):
        diagnosis = DiagnosisFactory(captured_at=datetime(2000, 1, 1, tzinfo=UTC))
        assert diagnosis.reported_at == diagnosis.received_at

    def test_uses_server_time_when_device_clock_is_far_in_the_future(self, taxonomy):
        diagnosis = DiagnosisFactory(captured_at=datetime.now(UTC) + timedelta(days=31))
        assert diagnosis.reported_at == diagnosis.received_at

    def test_a_few_days_ahead_is_still_trusted(self, taxonomy):
        diagnosis = DiagnosisFactory(captured_at=datetime.now(UTC) + timedelta(days=3))
        assert diagnosis.reported_at == diagnosis.captured_at


def test_photo_is_stored_by_client_id_not_phone_file_name(taxonomy, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    diagnosis = DiagnosisFactory()
    assert not diagnosis.has_photo
    diagnosis.photo.save("IMG_Mrs_Banda_farm.jpg", ContentFile(b"\xff\xd8fake"))
    assert diagnosis.has_photo
    assert diagnosis.photo.name == f"diagnoses/{diagnosis.farmer_id}/{diagnosis.client_id}.jpg"


class TestFeedback:
    def test_correct_feedback(self, taxonomy):
        FeedbackFactory().full_clean()

    def test_correction_only_allowed_when_wrong(self, taxonomy):
        feedback = FeedbackFactory.build(
            diagnosis=DiagnosisFactory(), corrected_disease=taxonomy["maize__common_rust"]
        )
        feedback.given_by = feedback.diagnosis.farmer
        with pytest.raises(ValidationError):
            feedback.full_clean()
        with pytest.raises(IntegrityError):
            feedback.save()

    def test_wrong_with_correction(self, taxonomy):
        feedback = FeedbackFactory(was_correct=False, corrected_disease=taxonomy["maize__common_rust"])
        assert "maize__common_rust" in str(feedback)

    def test_comment_limited_to_500_characters(self, taxonomy):
        feedback = FeedbackFactory.build(diagnosis=DiagnosisFactory(), comment="x" * 501)
        feedback.given_by = feedback.diagnosis.farmer
        with pytest.raises(ValidationError):
            feedback.full_clean()
