import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from build_labels import TAXONOMY, parse  # noqa: E402


def test_real_taxonomy_parses_with_one_healthy_class_per_crop():
    _, classes = parse(TAXONOMY.read_text(encoding="utf-8"))
    crops = {c["crop"] for c in classes}
    healthy = [c for c in classes if c["is_healthy"]]

    assert crops == {"maize", "groundnut", "cassava", "soybean", "cotton"}
    assert sorted(c["crop"] for c in healthy) == sorted(crops)


def test_out_of_order_indices_are_rejected():
    text = "# Taxonomy (DRAFT v0.1)\n| 0 | `maize__healthy` |\n| 2 | `maize__rust` |\n"
    with pytest.raises(ValueError, match="0..N-1"):
        parse(text)
