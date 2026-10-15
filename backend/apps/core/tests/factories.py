"""factory-boy factories shared by every app's tests. Each builds a valid object by default."""

import uuid
from datetime import UTC, datetime

import factory

from apps.accounts.models import Farmer
from apps.catalog.models import Disease, DiseaseAdvice
from apps.diagnoses.models import Diagnosis, Feedback
from apps.farms.models import Farm


class FarmerFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Farmer
        django_get_or_create = ["phone"]

    phone = factory.Sequence(lambda n: f"+26097{n:07d}")
    password = factory.django.Password(None)


class FarmFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Farm

    client_id = factory.LazyFunction(uuid.uuid4)
    owner = factory.SubFactory(FarmerFactory)
    name = factory.Sequence(lambda n: f"Field {n}")
    crops = factory.LazyFunction(lambda: ["maize"])


class DiseaseFactory(factory.django.DjangoModelFactory):
    """For tests that need an isolated disease. Most tests should use the `taxonomy` fixture instead."""

    class Meta:
        model = Disease
        django_get_or_create = ["class_id"]

    class_id = "maize__grey_leaf_spot"
    class_index = 2
    crop = "maize"
    is_healthy = False
    taxonomy_version = "0.1"


class DiseaseAdviceFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = DiseaseAdvice

    disease = factory.SubFactory(DiseaseFactory)
    lang = "en"
    name = "Grey Leaf Spot"
    symptoms = factory.LazyFunction(lambda: ["Long grey rectangular spots between the leaf veins."])
    treatment = factory.LazyFunction(
        lambda: {"title": "Now", "steps": ["Remove badly hit leaves."], "audio_url": None}
    )
    prevention = factory.LazyFunction(
        lambda: {"title": "Next season", "steps": ["Rotate crops."], "audio_url": None}
    )
    follow_up = factory.LazyFunction(
        lambda: {"title": "Check", "steps": ["Look again in 7 days."], "audio_url": None}
    )


class DiagnosisFactory(factory.django.DjangoModelFactory):
    """A confident grey leaf spot diagnosis. Needs the `taxonomy` fixture (or a DiseaseFactory)."""

    class Meta:
        model = Diagnosis

    client_id = factory.LazyFunction(uuid.uuid4)
    farmer = factory.SubFactory(FarmerFactory)
    crop = "maize"
    captured_at = factory.LazyFunction(lambda: datetime(2026, 11, 3, 9, 30, tzinfo=UTC))
    disease = factory.LazyFunction(lambda: Disease.objects.get(class_id="maize__grey_leaf_spot"))
    class_index = 2
    confidence = 0.91
    status = "confident"
    severity = "moderate"
    top_k = factory.LazyFunction(
        lambda: [
            {"class_id": "maize__grey_leaf_spot", "confidence": 0.91},
            {"class_id": "maize__northern_leaf_blight", "confidence": 0.06},
            {"class_id": "maize__common_rust", "confidence": 0.02},
        ]
    )
    model_version = "2026.11.0"
    inference_ms = 1840


class FeedbackFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Feedback

    client_id = factory.LazyFunction(uuid.uuid4)
    diagnosis = factory.SubFactory(DiagnosisFactory)
    given_by = factory.SelfAttribute("diagnosis.farmer")
    given_by_role = "farmer"
    was_correct = True
