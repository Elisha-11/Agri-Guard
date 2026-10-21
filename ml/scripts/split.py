"""Split the field photos into train / val / test by farmer, so no farmer's photos are in two splits (Step 4).

Usage:  python ml/scripts/split.py                       # all batches in ml/data/raw
        python ml/scripts/split.py --ratios 0.7 0.15 0.15

A farmer's split never changes once assigned: it is saved in ml/splits/farmers.csv (in git). New farmers are
added to whichever split keeps each class closest to the target ratios. Writes the per-photo list to
ml/data/processed/split.csv (DVC). Every batch must pass check_batch.py first. See docs/ml/splitting.md.
Standard library only.
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter, defaultdict
from pathlib import Path

from check_batch import ROOT, check_batch, load_classes

SPLITS = ("train", "val", "test")
RAW_DIR = ROOT / "ml" / "data" / "raw"
ASSIGNMENTS = ROOT / "ml" / "splits" / "farmers.csv"
OUT = ROOT / "ml" / "data" / "processed" / "split.csv"
MIN_EVAL_PHOTOS = 30  # fewer than this in val or test and that class's score means little


def read_batches(raw_dir):
    """Every photo row from every batch under raw_dir, with its batch name."""
    photos = []
    for csv_path in sorted(raw_dir.glob("*/metadata.csv")):
        with csv_path.open(encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                row = {k: (v or "").strip() for k, v in row.items() if k}
                photos.append({**row, "batch": csv_path.parent.name})
    return photos


def field_conflicts(photos):
    """check_batch.py catches a field under two farmers within a batch; this catches it across batches."""
    farmers = defaultdict(set)
    for photo in photos:
        farmers[photo["field_id"]].add(photo["farmer_code"])
    return [f"{field}: {', '.join(sorted(f))}" for field, f in sorted(farmers.items()) if len(f) > 1]


def label(photo):
    return photo.get("suspected_class") or "unknown"


def read_assignments(path):
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8", newline="") as f:
        return {row["farmer_code"]: row["split"] for row in csv.DictReader(f)}


def assign(photos, existing, ratios):
    """farmer_code -> split. Existing farmers keep their split; new ones are placed greedily, largest first.

    Each new farmer goes where the squared distance between every class's per-split count and its target
    (ratio x class total) ends up smallest. No randomness: the same input always gives the same split.
    """
    per_farmer = defaultdict(Counter)
    for photo in photos:
        per_farmer[photo["farmer_code"]][label(photo)] += 1
    totals = Counter()
    for counts in per_farmer.values():
        totals.update(counts)
    target = {s: {c: r * n for c, n in totals.items()} for s, r in zip(SPLITS, ratios, strict=True)}

    assignment = dict(existing)
    current = {s: Counter() for s in SPLITS}
    for farmer, counts in per_farmer.items():
        if farmer in assignment:
            current[assignment[farmer]].update(counts)

    def cost(split, counts):
        return sum(
            (current[split][c] + counts[c]) ** 2 - current[split][c] ** 2 - 2 * target[split][c] * counts[c]
            for c in counts
        )  # the change in sum((count - target)^2) from adding `counts` to `split`

    new = [f for f in per_farmer if f not in assignment]
    for farmer in sorted(new, key=lambda f: (-sum(per_farmer[f].values()), f)):
        counts = per_farmer[farmer]
        best = min(SPLITS, key=lambda s: (cost(s, counts), SPLITS.index(s)))
        assignment[farmer] = best
        current[best].update(counts)
    return assignment, current


def write_csv(path, fieldnames, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def summary(current, classes):
    """Lines with photos per class per split, and warnings for classes that can't be evaluated."""
    lines = [f"{'class':40s} {'train':>6s} {'val':>6s} {'test':>6s}"]
    warnings = []
    for class_id in sorted({c for counts in current.values() for c in counts}):
        n = [current[s][class_id] for s in SPLITS]
        lines.append(f"{class_id:40s} {n[0]:6d} {n[1]:6d} {n[2]:6d}")
        if class_id in classes and min(n[1], n[2]) < MIN_EVAL_PHOTOS:
            warnings.append(
                f"WARN  {class_id}: under {MIN_EVAL_PHOTOS} photos in val or test (more farmers needed)"
            )
    lines.append(f"{'total':40s} " + " ".join(f"{sum(current[s].values()):6d}" for s in SPLITS))
    return lines, warnings


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--raw-dir", type=Path, default=RAW_DIR)
    parser.add_argument("--assignments", type=Path, default=ASSIGNMENTS)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument(
        "--ratios", type=float, nargs=3, default=[0.7, 0.15, 0.15], metavar=("TRAIN", "VAL", "TEST")
    )
    args = parser.parse_args(argv)
    if abs(sum(args.ratios) - 1) > 1e-9 or min(args.ratios) <= 0:
        parser.error("--ratios must be three positive numbers adding up to 1")

    classes = load_classes()
    batches = sorted(p.parent for p in args.raw_dir.glob("*/metadata.csv"))
    if not batches:
        print(f"No batches with a metadata.csv in {args.raw_dir}")
        return 1
    failed = [b.name for b in batches if check_batch(b, classes).errors]
    if failed:
        print("These batches have errors; fix them first (python ml/scripts/check_batch.py <batch>):")
        print("\n".join(f"  {name}" for name in failed))
        return 1

    photos = read_batches(args.raw_dir)
    conflicts = field_conflicts(photos)
    if conflicts:
        print("Fields listed under more than one farmer across batches; fix the codes first:")
        print("\n".join(f"  {line}" for line in conflicts))
        return 1
    existing = read_assignments(args.assignments)
    bad = sorted({s for s in existing.values() if s not in SPLITS})
    if bad:
        print(f"{args.assignments} has unknown splits: {', '.join(bad)}")
        return 1
    assignment, current = assign(photos, existing, args.ratios)

    write_csv(
        args.assignments,
        ["farmer_code", "split"],
        [{"farmer_code": f, "split": s} for f, s in sorted(assignment.items())],
    )
    columns = ["batch", "filename", "split", "farmer_code", "field_id", "crop", "suspected_class"]
    write_csv(
        args.out,
        columns,
        [{**{c: p.get(c, "") for c in columns}, "split": assignment[p["farmer_code"]]} for p in photos],
    )

    added = len(assignment) - len(existing)
    lines, warnings = summary(current, classes)
    print("\n".join(lines + [""] + warnings))
    print(f"\n{len(photos)} photos, {len(assignment)} farmers ({added} new).")
    print(f"Wrote {args.out} and {args.assignments}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
