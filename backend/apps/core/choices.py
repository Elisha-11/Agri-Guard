"""Enumerations shared by several apps.

Each one mirrors an enum in docs/api-contract.yaml. If you change a value here, change the contract in the
same PR (following the contract rules in CONTRIBUTING.md). apps/core/tests/test_contract_alignment.py checks
that they match.
"""

from django.db import models


class Language(models.TextChoices):
    """Contract schema `Language`."""

    ENGLISH = "en", "English"
    NYANJA = "ny", "Nyanja (Chichewa)"
    BEMBA = "bem", "Bemba"
    TONGA = "toi", "Tonga"


class Crop(models.TextChoices):
    """Contract schema `Crop`."""

    MAIZE = "maize", "Maize"
    GROUNDNUT = "groundnut", "Groundnut"
    CASSAVA = "cassava", "Cassava"
    SOYBEAN = "soybean", "Soybean"
    COTTON = "cotton", "Cotton"


class Role(models.TextChoices):
    """Contract `Farmer.role` and `FeedbackCreate.given_by_role`."""

    FARMER = "farmer", "Farmer"
    EXTENSION_OFFICER = "extension_officer", "Extension officer"


class PredictionStatus(models.TextChoices):
    """Contract `Prediction.status`; thresholds are in docs/model-output.md §4."""

    CONFIDENT = "confident", "Confident"
    UNCERTAIN = "uncertain", "Uncertain"
    CONSULT = "consult", "Consult an extension officer"


class Severity(models.TextChoices):
    """Contract `Prediction.severity`; see docs/model-output.md §5."""

    NONE = "none", "None (healthy)"
    LOW = "low", "Low"
    MODERATE = "moderate", "Moderate"
    HIGH = "high", "High"
    UNKNOWN = "unknown", "Unknown"
