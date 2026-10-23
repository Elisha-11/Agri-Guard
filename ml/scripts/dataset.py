"""Dataset logic for baseline training, kept free of TensorFlow so CI can test it (docs/ml/training.md).

Covers: the mapping CSV (source folder -> our class id), scanning a folder-per-class image tree, choosing
the split (by farmer/field when metadata has them, stratified random otherwise), class weights, the per-class
metrics and confusion matrix, and the run config written next to each run. Standard library only.
"""

from __future__ import annotations

import csv
import hashlib
import json
import random
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from split import SPLITS
from split import assign as assign_groups

ROOT = Path(__file__).resolve().parents[2]
LABELS = ROOT / "ml" / "labels.json"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}
DEFAULT_RATIOS = (0.7, 0.15, 0.15)


class DatasetError(ValueError):
    """The input can't be used as given. The message lists every problem found, one per line."""

    def __init__(self, problems):
        self.problems = list(problems)
        super().__init__("\n".join(self.problems))


# --- labels -------------------------------------------------------------------------------------------------


def load_labels(path=LABELS):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def class_ids(labels):
    """Class ids in output-layer order. The model's output unit i is labels.json's class with index i."""
    classes = labels["classes"]
    indices = [c["index"] for c in classes]
    if indices != list(range(len(classes))):
        raise DatasetError([f"labels.json indices must be 0..N-1 in order, got {indices}"])
    ids = [c["id"] for c in classes]
    if len(set(ids)) != len(ids):
        raise DatasetError(["labels.json has duplicate class ids"])
    return ids


def check_output_order(model_classes, labels):
    """The model's class list (as trained) must be labels.json's, index for index. Returns the problems."""
    expected = class_ids(labels)
    if list(model_classes) == expected:
        return []
    if len(model_classes) != len(expected):
        return [f"model has {len(model_classes)} outputs, labels.json has {len(expected)} classes"]
    return [
        f"output {i} is {got!r}, labels.json says {want!r}"
        for i, (got, want) in enumerate(zip(model_classes, expected, strict=True))
        if got != want
    ]


# --- mapping CSV and folder scan ----------------------------------------------------------------------------


def parse_mapping(path, known_ids):
    """Read `source,class_id` rows. Returns {source folder name: class id, or None to skip that folder}.

    Several sources may map to one class (e.g. two public datasets' rust folders). An empty class_id, or
    `skip`, means "ignore this folder". Every problem is reported at once.
    """
    problems, mapping = [], {}
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or not {"source", "class_id"} <= set(reader.fieldnames):
            raise DatasetError([f"{Path(path).name}: needs the columns source,class_id"])
        for line, row in enumerate(reader, start=2):
            source = (row.get("source") or "").strip()
            target = (row.get("class_id") or "").strip()
            if not source:
                problems.append(f"mapping line {line}: empty source")
                continue
            target = None if target in ("", "skip") else target
            if target is not None and target not in known_ids:
                problems.append(f"mapping line {line}: {target!r} is not a class id in labels.json")
            if source in mapping and mapping[source] != target:
                problems.append(f"mapping line {line}: {source!r} is mapped twice, to different classes")
            mapping[source] = target
    if problems:
        raise DatasetError(problems)
    return mapping


@dataclass
class Item:
    """One training image. `path` is relative to the images folder, with forward slashes."""

    path: str
    class_id: str
    group: str = ""  # farmer_code (or field_id) when known
    split: str = ""


@dataclass
class Scan:
    items: list[Item]
    skipped: dict[str, int] = field(default_factory=dict)  # source folder -> images ignored
    empty: list[str] = field(default_factory=list)  # class ids with no images, in labels.json order


def scan_images(images_dir, mapping, ids):
    """Every image under images_dir/<source>/ (any depth), labelled through the mapping.

    A folder missing from the mapping is an error, so nothing is silently dropped or mislabelled.
    """
    images_dir = Path(images_dir)
    if not images_dir.is_dir():
        raise DatasetError([f"{images_dir} is not a folder"])
    folders = sorted(p for p in images_dir.iterdir() if p.is_dir())
    unmapped = [p.name for p in folders if p.name not in mapping]
    if unmapped:
        raise DatasetError([f"folder {name!r} is not in the mapping CSV" for name in unmapped])

    items, skipped = [], {}
    for folder in folders:
        files = sorted(p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES)
        target = mapping[folder.name]
        if target is None:
            skipped[folder.name] = len(files)
            continue
        items += [Item(p.relative_to(images_dir).as_posix(), target) for p in files]
    present = {i.class_id for i in items}
    return Scan(items, skipped, [c for c in ids if c not in present])


# --- splits -------------------------------------------------------------------------------------------------


def stratified_split(items, ratios=DEFAULT_RATIOS, seed=42):
    """Random split per class (public data only: it can put look-alike photos in train and test).

    Deterministic for a seed. A class with at least 3 images gets at least one in val and one in test.
    """
    by_class = defaultdict(list)
    for item in items:
        by_class[item.class_id].append(item)
    for class_id, members in sorted(by_class.items()):
        members.sort(key=lambda i: i.path)
        random.Random(f"{seed}:{class_id}").shuffle(members)
        n = len(members)
        n_val, n_test = round(n * ratios[1]), round(n * ratios[2])
        if n >= 3:
            n_val, n_test = max(n_val, 1), max(n_test, 1)
        for k, item in enumerate(members):
            item.split = "val" if k < n_val else "test" if k < n_val + n_test else "train"
    return items


def read_metadata(path):
    """Rows keyed by `path` (relative to the images folder) or, failing that, by `filename`.

    Recognised columns: farmer_code, field_id (the group), split (used as given). Filenames must be unique
    when used as the key, since camera names like IMG_0001.jpg repeat across batches.
    """
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        columns = set(reader.fieldnames or [])
        rows = [{k: (v or "").strip() for k, v in row.items() if k} for row in reader]
    key = "path" if "path" in columns else "filename" if "filename" in columns else None
    if key is None:
        raise DatasetError([f"{Path(path).name}: needs a path or filename column"])
    if not columns & {"farmer_code", "field_id", "split"}:
        raise DatasetError([f"{Path(path).name}: needs farmer_code, field_id or split"])
    keyed, duplicates = {}, set()
    for row in rows:
        if row[key] in keyed:
            duplicates.add(row[key])
        keyed[row[key]] = row
    if duplicates:
        raise DatasetError([f"metadata lists {key} {d!r} more than once" for d in sorted(duplicates)])
    return key, keyed


def grouped_split(items, metadata, ratios=DEFAULT_RATIOS):
    """Split by farmer (or field when there's no farmer code), never by photo.

    A `split` column in the metadata (e.g. ml/data/processed/split.csv) is used as given; otherwise groups are
    placed with the same logic as split.py. Returns the method name: "metadata", "farmer" or "field".
    """
    key, rows = metadata
    problems = []
    for item in items:
        row = rows.get(item.path if key == "path" else Path(item.path).name)
        if row is None:
            problems.append(f"{item.path}: not in the metadata")
            continue
        item.group = row.get("farmer_code") or row.get("field_id") or ""
        item.split = row.get("split", "")
        if item.split and item.split not in SPLITS:
            problems.append(f"{item.path}: split {item.split!r} is not train, val or test")
        if not item.split and not item.group:
            problems.append(f"{item.path}: no farmer_code, field_id or split")
    if problems:
        raise DatasetError(
            problems[:50] + ([f"... and {len(problems) - 50} more"] if len(problems) > 50 else [])
        )

    if all(i.split for i in items):
        method = "metadata"
    else:
        any_row = next(iter(rows.values()), {})
        method = "farmer" if any_row.get("farmer_code") else "field"
        photos = [{"farmer_code": i.group, "suspected_class": i.class_id} for i in items]
        existing = {i.group: i.split for i in items if i.split and i.group}
        assignment, _ = assign_groups(photos, existing, ratios)
        for item in items:
            item.split = item.split or assignment[item.group]

    splits_of = defaultdict(set)
    for item in items:
        if item.group:
            splits_of[item.group].add(item.split)
    leaks = sorted(g for g, s in splits_of.items() if len(s) > 1)
    if leaks:
        raise DatasetError([f"group {g} is in more than one split: {sorted(splits_of[g])}" for g in leaks])
    return method


def smoke_sample(items, n=20, seed=42):
    """About n images spread over the classes (round robin), for --smoke."""
    by_class = defaultdict(list)
    for item in sorted(items, key=lambda i: i.path):
        by_class[item.class_id].append(item)
    rng = random.Random(seed)
    for members in by_class.values():
        rng.shuffle(members)
    picked, round_no = [], 0
    while len(picked) < n and any(round_no < len(m) for m in by_class.values()):
        for class_id in sorted(by_class):
            if round_no < len(by_class[class_id]) and len(picked) < n:
                picked.append(by_class[class_id][round_no])
        round_no += 1
    return picked


def split_counts(items, ids):
    """{class_id: {"train": n, "val": n, "test": n}} for every class in labels.json, zeros included."""
    counts = {c: dict.fromkeys(SPLITS, 0) for c in ids}
    for item in items:
        counts[item.class_id][item.split] += 1
    return counts


def class_weights(items, ids):
    """{output index: weight} for every class, so each class present in train counts equally in the loss.

    Classes with no training images get 1.0: they never occur in a batch, but Keras looks weights up by index.
    """
    train = Counter(i.class_id for i in items if i.split == "train")
    total, present = sum(train.values()), len(train)
    return {k: total / (present * train[c]) if train[c] else 1.0 for k, c in enumerate(ids)}


# --- metrics ------------------------------------------------------------------------------------------------


def confusion_matrix(y_true, y_pred, n):
    """n x n counts; row = true class index, column = predicted class index."""
    matrix = [[0] * n for _ in range(n)]
    for t, p in zip(y_true, y_pred, strict=True):
        matrix[t][p] += 1
    return matrix


def per_class_metrics(matrix, ids):
    """Precision, recall and F1 per class from a confusion matrix. None where undefined (no support / no
    predictions), so "no data" is never confused with a score of 0."""
    rows = []
    for k, class_id in enumerate(ids):
        tp = matrix[k][k]
        support = sum(matrix[k])
        predicted = sum(row[k] for row in matrix)
        precision = tp / predicted if predicted else None
        recall = tp / support if support else None
        f1 = (
            2 * precision * recall / (precision + recall)
            if precision is not None and recall is not None and precision + recall
            else (0.0 if precision is not None and recall is not None else None)
        )
        rows.append(
            {"class_id": class_id, "precision": precision, "recall": recall, "f1": f1, "support": support}
        )
    return rows


def summary_metrics(matrix, per_class):
    total = sum(map(sum, matrix))
    correct = sum(matrix[k][k] for k in range(len(matrix)))
    supported = [r for r in per_class if r["support"]]
    return {
        "accuracy": correct / total if total else None,
        "macro_recall": sum(r["recall"] for r in supported) / len(supported) if supported else None,
        "macro_f1": sum(r["f1"] or 0 for r in supported) / len(supported) if supported else None,
        "classes_evaluated": len(supported),
        "images": total,
    }


def write_metrics_csv(path, per_class):
    with Path(path).open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["class_id", "precision", "recall", "f1", "support"], lineterminator="\n"
        )
        writer.writeheader()
        for row in per_class:
            writer.writerow(
                {
                    k: ("no data" if v is None else round(v, 4) if isinstance(v, float) else v)
                    for k, v in row.items()
                }
            )


def write_confusion_csv(path, matrix, ids):
    with Path(path).open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["true \\ predicted", *ids])
        for class_id, row in zip(ids, matrix, strict=True):
            writer.writerow([class_id, *row])


# --- run config ---------------------------------------------------------------------------------------------


def sha256_of(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest() if path else None


def run_config(flags, *, split_method, counts, empty, skipped, versions, git):
    """Everything needed to understand (and redo) a run, written to <run>/run_config.json."""
    return {
        "flags": {k: (str(v) if isinstance(v, Path) else v) for k, v in sorted(flags.items())},
        "seed": flags.get("seed"),
        "model_version": flags.get("model_version"),
        "split_method": split_method,
        "mapping_sha256": sha256_of(flags.get("mapping")),
        "images_per_class": counts,
        "totals": {s: sum(c[s] for c in counts.values()) for s in SPLITS},
        "classes_without_images": empty,
        "skipped_folders": skipped,
        "versions": versions,
        "git": git,
    }
