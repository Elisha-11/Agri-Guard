"""Check API responses against the schemas in docs/api-contract.yaml.

    from apps.core.tests.contract import assert_matches_contract
    assert_matches_contract(response.json(), "Farmer")

If the backend and the contract disagree on a field name, type, enum or required field, the test fails, so
drift shows up in the PR that causes it rather than on a farmer's phone.
"""

from functools import cache
from pathlib import Path

import yaml
from django.conf import settings
from jsonschema import Draft202012Validator, FormatChecker

CONTRACT_PATH = Path(settings.BASE_DIR).parent / "docs" / "api-contract.yaml"


@cache
def contract():
    return yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))


def assert_matches_contract(data, schema_name, *, many=False):
    """Validate `data` against `components.schemas.<schema_name>` (OpenAPI 3.1 = JSON Schema 2020-12)."""
    doc = contract()
    assert schema_name in doc["components"]["schemas"], f"No schema {schema_name!r} in the contract"
    ref = {"$ref": f"#/components/schemas/{schema_name}"}
    # Validate with the whole contract as the root document, so internal $refs resolve.
    schema = {**doc, **({"type": "array", "items": ref} if many else ref)}
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(data), key=lambda e: list(e.path))
    assert not errors, "\n".join(f"{list(e.path)}: {e.message}" for e in errors)
