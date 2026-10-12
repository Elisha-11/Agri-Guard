"""Generate ml/labels.json from docs/class-taxonomy.md so the model and the PWA never disagree on class order.

Usage:  python ml/scripts/build_labels.py [--model-version 2026.11.0]
Standard library only.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TAXONOMY = ROOT / "docs" / "class-taxonomy.md"
OUT = ROOT / "ml" / "labels.json"

ROW = re.compile(r"^\|\s*(\d+)\s*\|\s*`([a-z]+__[a-z_]+)`\s*\|")
VERSION = re.compile(r"Taxonomy \(DRAFT v([\d.]+)\)|Taxonomy v([\d.]+)")


def parse(text: str) -> tuple[str, list[dict]]:
    match = VERSION.search(text)
    if not match:
        raise ValueError("taxonomy version not found in title")
    version = match.group(1) or match.group(2)

    classes = []
    for line in text.splitlines():
        row = ROW.match(line)
        if not row:
            continue
        index, class_id = int(row.group(1)), row.group(2)
        crop, condition = class_id.split("__", 1)
        classes.append({"index": index, "id": class_id, "crop": crop, "is_healthy": condition == "healthy"})

    indices = [c["index"] for c in classes]
    if indices != list(range(len(classes))):
        raise ValueError(f"class indices must be 0..N-1 in order, got {indices}")
    ids = [c["id"] for c in classes]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate class ids")
    return version, classes


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-version", default="0.0.0-untrained")
    args = parser.parse_args()

    version, classes = parse(TAXONOMY.read_text(encoding="utf-8"))
    labels = {
        "model_version": args.model_version,
        "taxonomy_version": version,
        "input": {
            "width": 224,
            "height": 224,
            "channels": 3,
            "preprocessing": "efficientnet",
            "value_range": [0, 255],
        },
        "classes": classes,
    }
    OUT.write_text(json.dumps(labels, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(classes)} classes, taxonomy v{version}")


if __name__ == "__main__":
    main()
