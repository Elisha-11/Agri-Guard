"""The backend's enums and validators must match docs/api-contract.yaml exactly. These tests catch drift."""

from pathlib import Path

import pytest
import yaml
from django.conf import settings

from apps.core import choices
from apps.core.validators import PHONE_REGEX

CONTRACT = yaml.safe_load((Path(settings.BASE_DIR).parent / "docs" / "api-contract.yaml").read_text("utf-8"))
SCHEMAS = CONTRACT["components"]["schemas"]


@pytest.mark.parametrize(
    "enum, contract_values",
    [
        (choices.Language, SCHEMAS["Language"]["enum"]),
        (choices.Crop, SCHEMAS["Crop"]["enum"]),
        (choices.Role, SCHEMAS["Farmer"]["properties"]["role"]["enum"]),
        (choices.Role, SCHEMAS["FeedbackCreate"]["properties"]["given_by_role"]["enum"]),
        (choices.PredictionStatus, SCHEMAS["Prediction"]["properties"]["status"]["enum"]),
        (choices.Severity, SCHEMAS["Prediction"]["properties"]["severity"]["enum"]),
    ],
)
def test_enum_matches_contract(enum, contract_values):
    assert list(enum.values) == contract_values


def test_phone_pattern_matches_contract():
    assert PHONE_REGEX == SCHEMAS["PhoneNumber"]["pattern"]
