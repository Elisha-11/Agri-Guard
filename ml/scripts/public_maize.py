"""Turn downloaded public maize datasets into a cleaned, mapped, grouped and split image set.

Usage:  python ml/scripts/public_maize.py                       # every usable source in ml/data/external
        python ml/scripts/public_maize.py --test-source zmld    # hold one source out as the whole test set

Reads ml/data/external/<source>/extracted/ (fetch_public.py) and writes ml/data/interim/public_maize/:

    <class_id>/<source>__<sha12>.<ext>    kept images, copied byte for byte (never re-encoded)
    unmapped/<source>/<label>/...         images whose label has no class yet (e.g. fall armyworm)
    metadata.csv                          ml/templates/metadata.csv columns + source, licence, original_label
    unmapped/metadata.csv                 the same, for the unmapped images
    split.csv                             filename, field_id, split (read by train_baseline.py --metadata)
    training_mapping.csv                  for train_baseline.py --mapping (class folders; unmapped skipped)
    report.md                             counts per class and source, what was dropped and why, gaps

Rules (docs/ml/public-datasets.md):
- Labels go through ml/mappings/<source>.csv. A label with an empty class_id is kept aside in unmapped/,
  never guessed. Rows marked `confirm=agronomist` are listed in the report.
- Dropped: augmented copies (by name), unreadable files, images under 224 px on the short side
  (check_batch.py's minimum), exact duplicates (SHA-256) and near-duplicates (dHash distance <= 4),
  across sources too. The copy from the higher-priority source is kept.
- Grouping: images within dHash distance 12 of each other (the same leaf or scene, even across sources)
  share a group code in `field_id`, and whole groups are placed by split.py's assign(), so look-alikes
  never straddle train and test. Lab-style sources (PlantVillage-like) are always train, never val/test.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
import shutil
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from dataset import IMAGE_SUFFIXES, class_ids, load_labels, parse_mapping
from split import SPLITS
from split import assign as assign_groups

ROOT = Path(__file__).resolve().parents[2]
EXTERNAL = ROOT / "ml" / "data" / "external"
MAPPINGS = ROOT / "ml" / "mappings"
TEMPLATE = ROOT / "ml" / "templates" / "metadata.csv"
OUT = ROOT / "ml" / "data" / "interim" / "public_maize"

MIN_SIDE, SMALL_SIDE = 224, 600  # same as check_batch.py
DROP_DISTANCE = 4  # dHash bits: this close is the same photo (resized, re-saved, lightly edited)
GROUP_DISTANCE = 12  # this close is very likely the same leaf or scene: keep in one split
MIN_TRAINABLE = 300  # class-taxonomy.md: a class needs >= 300 reviewed images
EXTRA_COLUMNS = ["source", "licence", "original_label"]
TARGET_CLASSES = [
    "maize__healthy",
    "maize__northern_leaf_blight",
    "maize__grey_leaf_spot",
    "maize__common_rust",
    "maize__lethal_necrosis",
    "maize__streak_virus",
]
AUGMENTED = re.compile(
    r"(^|[\\/_\- .])"
    r"(aug|augment(ed)?|rot(ated)?\d*|flip(ped)?|mirror(ed)?|bright(ness)?|zoom(ed)?|crop(ped)?\d+)"
    r"([\\/_\- .]|\d|$)",
    re.IGNORECASE,
)


def _strip_number(name):
    return re.sub(r"_\d+$", "", name)


# How each source is read. `label_of` gets the image path relative to <source>/extracted/ and returns the
# source's own label. `priority`: lower wins when the same photo is in two sources.
SOURCES = {
    "karaagro": {
        "priority": 2,
        "licence": "CC0-1.0",
        "lab": False,
        "label_of": lambda rel: _strip_number(rel.parts[0]),  # healthy_01/... -> healthy
    },
    "tanzania": {
        "priority": 3,
        "licence": "CC-BY-4.0",
        "lab": False,
        "label_of": lambda rel: next((p for p in rel.parts if p.upper() in {"HEALTHY", "MLN", "MSV"}), ""),
    },
    "ghana_mendeley": {
        "priority": 4,
        "licence": "CC-BY-4.0",
        "lab": False,  # mixed backgrounds; review before allowing any of it into val/test
        "label_of": lambda rel: rel.parent.name.lower(),
    },
    "zmld": {
        "priority": 1,
        "licence": "CC-BY-4.0",
        "lab": False,
        "exclude": (
            "Zenodo upload (2026-01-30) holds 1,388 of the 19,990 images described; 825 are the Kaggle/"
            "PlantVillage 'Corn_Gray_Spot' set (751 at 256x256), and the same photos carry different labels "
            "in train and test. Unusable until the author publishes the full, consistent set."
        ),
        "label_of": lambda rel: "",
    },
}


# --- hashing ------------------------------------------------------------------------------------------------


def sha256_of(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def dhash_bits(gray_9x8):
    """64-bit difference hash from 72 grayscale values (9 wide x 8 high, row by row)."""
    bits = 0
    for row in range(8):
        for col in range(8):
            left, right = gray_9x8[row * 9 + col], gray_9x8[row * 9 + col + 1]
            bits = (bits << 1) | (1 if left > right else 0)
    return bits


def hamming(a, b):
    return (a ^ b).bit_count()


def near_pairs(hashes, distance):
    """Index pairs (i, j), i < j, whose hashes differ in at most `distance` bits.

    Pigeonhole: split the 64 bits into distance+1 chunks; two hashes within `distance` bits agree exactly
    on at least one chunk. Only hashes sharing a chunk are compared, so this stays fast for ~10^5 images.
    """
    chunks = distance + 1
    bounds = [round(k * 64 / chunks) for k in range(chunks + 1)]
    pairs = set()
    for k in range(chunks):
        lo, hi = bounds[k], bounds[k + 1]
        mask = (1 << (hi - lo)) - 1
        buckets = defaultdict(list)
        for i, h in enumerate(hashes):
            buckets[(h >> lo) & mask].append(i)
        for members in buckets.values():
            for a in range(len(members)):
                for b in range(a + 1, len(members)):
                    i, j = members[a], members[b]
                    if (i, j) not in pairs and hamming(hashes[i], hashes[j]) <= distance:
                        pairs.add((i, j))
    return sorted(pairs)


class UnionFind:
    def __init__(self, n):
        self.parent = list(range(n))

    def find(self, x):
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[max(ra, rb)] = min(ra, rb)


# --- the pipeline -------------------------------------------------------------------------------------------


@dataclass
class Candidate:
    source: str
    path: Path  # absolute
    rel: str  # relative to <source>/extracted, forward slashes
    original_label: str
    class_id: str | None = None  # None: unmapped
    sha256: str = ""
    dhash: int = 0
    width: int = 0
    height: int = 0
    captured_at: str = ""
    dropped: str = ""  # reason, empty when kept
    duplicate_of: str = ""
    group: str = ""
    split: str = ""
    filename: str = ""
    warnings: list[str] = field(default_factory=list)


def read_mapping_file(path, known_ids):
    """{source label: class id or None} plus the labels that need agronomist confirmation."""
    mapping = parse_mapping(path, known_ids)
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        confirm = {
            (r.get("source") or "").strip(): (r.get("note") or "").strip()
            for r in csv.DictReader(f)
            if (r.get("confirm") or "").strip()
        }
    return mapping, confirm


ROBOFLOW = re.compile(r"^(?P<original>.+)\.rf\.[0-9a-f]{16,}$", re.IGNORECASE)


def original_photo(path):
    """The photo a file was exported from. Roboflow names exports `<original>_jpeg.rf.<hash>.jpg` and
    exports augmented variants of one photo under different hashes; any other file is its own original."""
    match = ROBOFLOW.match(Path(path).stem)
    return match["original"] if match else Path(path).stem


def discover(source, extracted, mapping):
    """Every image file under <source>/extracted, with its source label and our class id."""
    config = SOURCES[source]
    found, exported = [], set()
    for path in sorted(p for p in Path(extracted).rglob("*") if p.is_file()):
        if path.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        rel = path.relative_to(extracted)
        label = config["label_of"](rel)
        c = Candidate(source, path, rel.as_posix(), label)
        original = (rel.parent.as_posix(), original_photo(path))
        if AUGMENTED.search(rel.as_posix()):
            c.dropped = "augmented"
        elif original in exported:
            c.dropped = "augmented (second Roboflow export of one photo)"
        elif label not in mapping:
            c.dropped = "label not in mapping"
        else:
            c.class_id = mapping[label]
        if not c.dropped:
            exported.add(original)
        found.append(c)
    return found


def inspect_image(c):
    """Fill size, hashes and capture time from the file; mark it dropped if unreadable or too small."""
    from PIL import Image, UnidentifiedImageError  # only needed when real images are read

    try:
        with Image.open(c.path) as im:
            im.verify()
        with Image.open(c.path) as im:
            c.width, c.height = im.size
            exif = im.getexif()
            stamp = exif.get(36867) or exif.get(306)  # DateTimeOriginal, else DateTime
            if stamp:
                try:
                    c.captured_at = datetime.strptime(str(stamp), "%Y:%m:%d %H:%M:%S").strftime(
                        "%Y-%m-%d %H:%M"
                    )
                except ValueError:
                    pass
            small = im.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
            c.dhash = dhash_bits(small.tobytes())  # 72 grayscale bytes, row by row
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError):
        c.dropped = "corrupt"
        return c
    if min(c.width, c.height) < MIN_SIDE:
        c.dropped = f"under {MIN_SIDE} px"
    elif min(c.width, c.height) < SMALL_SIDE:
        c.warnings.append(f"under {SMALL_SIDE} px")
    c.sha256 = sha256_of(c.path)
    return c


def drop_duplicates(candidates):
    """Exact (SHA-256) then near (dHash <= DROP_DISTANCE) duplicates; the higher-priority copy stays."""
    live = [c for c in candidates if not c.dropped]
    live.sort(key=lambda c: (SOURCES[c.source]["priority"], c.source, c.rel))

    first = {}
    for c in live:
        if c.sha256 in first:
            c.dropped, c.duplicate_of = "exact duplicate", f"{first[c.sha256].source}:{first[c.sha256].rel}"
        else:
            first[c.sha256] = c

    live = [c for c in live if not c.dropped]
    uf = UnionFind(len(live))
    for i, j in near_pairs([c.dhash for c in live], DROP_DISTANCE):
        uf.union(i, j)  # union keeps the lower index, i.e. the higher-priority copy, as the root
    for i, c in enumerate(live):
        root = uf.find(i)
        if root != i:
            keep = live[root]
            c.dropped, c.duplicate_of = "near duplicate", f"{keep.source}:{keep.rel}"
    return candidates


def assign_group_codes(kept):
    """Group look-alikes (dHash <= GROUP_DISTANCE, any source). Codes match check_batch.py's CODE format."""
    uf = UnionFind(len(kept))
    for i, j in near_pairs([c.dhash for c in kept], GROUP_DISTANCE):
        uf.union(i, j)
    numbers = {}
    for i, c in enumerate(kept):
        root = uf.find(i)
        numbers.setdefault(root, len(numbers) + 1)
        c.group = f"PUB-{numbers[root]:06d}"
    return kept


def assign_splits(kept, test_sources=(), ratios=(0.7, 0.15, 0.15)):
    """Whole groups go to one split.

    - A group containing a lab-style image is train (lab photos never measure field performance).
    - A group containing an image from a `test_sources` source is test. When a test source is given, the
      other groups are split train/val only, so the test set is that source alone.
    - The rest are placed by split.py's assign() (deterministic, balanced per class).
    """
    groups = defaultdict(list)
    for c in kept:
        groups[c.group].append(c)

    fixed, free = {}, []
    for code, members in groups.items():
        if any(SOURCES[c.source]["lab"] for c in members):
            fixed[code] = "train"
        elif any(c.source in test_sources for c in members):
            fixed[code] = "test"
        else:
            free.append(code)

    if test_sources:
        ratios = (ratios[0] / (ratios[0] + ratios[1]), ratios[1] / (ratios[0] + ratios[1]), 0.0)
    photos = [{"farmer_code": c.group, "suspected_class": c.class_id} for c in kept if c.group in set(free)]
    placed, _ = assign_groups(photos, {}, ratios) if photos else ({}, None)
    for c in kept:
        c.split = fixed.get(c.group) or placed[c.group]
    return kept


def metadata_row(c, columns):
    row = dict.fromkeys(columns, "")
    row.update(
        filename=c.filename,
        crop="maize",
        suspected_class=c.class_id or "unknown",
        stage="unknown",
        field_id=c.group,
        captured_at=c.captured_at,
        notes="; ".join([f"original: {c.rel}", *c.warnings]),
        source=c.source,
        licence=SOURCES[c.source]["licence"],
        original_label=c.original_label,
    )
    return row


def template_columns(path=TEMPLATE):
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        return next(csv.reader(f)) + EXTRA_COLUMNS


def report_markdown(candidates, excluded, confirm, test_sources, now=None):
    now = now or datetime.now(UTC)
    kept = [c for c in candidates if not c.dropped and c.class_id]
    unmapped = [c for c in candidates if not c.dropped and not c.class_id]
    sources = sorted({c.source for c in candidates})
    lines = [
        "# Public maize dataset report",
        "",
        f"Generated {now:%Y-%m-%d %H:%M} UTC by `ml/scripts/public_maize.py`."
        + (f" Test set: {', '.join(test_sources)} only." if test_sources else ""),
        "",
        "## Kept images per class and source",
        "",
        "| Class | " + " | ".join(sources) + " | Total | Train | Val | Test |",
        "|---|" + "---|" * (len(sources) + 4),
    ]
    by = Counter((c.class_id, c.source) for c in kept)
    splits = Counter((c.class_id, c.split) for c in kept)
    totals = Counter(c.class_id for c in kept)
    for cls in TARGET_CLASSES:
        cells = [str(by[(cls, s)]) for s in sources]
        lines.append(
            f"| `{cls}` | "
            + " | ".join(cells)
            + f" | **{totals[cls]}** | "
            + " | ".join(str(splits[(cls, s)]) for s in SPLITS)
            + " |"
        )
    lines += ["", f"Unmapped, kept aside in `unmapped/`: {len(unmapped)}"]
    for (src, label), n in sorted(Counter((c.source, c.original_label) for c in unmapped).items()):
        lines.append(f"- {src} / {label}: {n}")

    lines += ["", "## Dropped", "", "| Source | Reason | Images |", "|---|---|---|"]
    for (src, reason), n in sorted(Counter((c.source, c.dropped) for c in candidates if c.dropped).items()):
        lines.append(f"| {src} | {reason} | {n} |")
    cross = sum(1 for c in candidates if c.duplicate_of and not c.duplicate_of.startswith(f"{c.source}:"))
    lines.append(f"\nDuplicates found across sources: {cross}.")

    if excluded:
        lines += ["", "## Sources excluded", ""] + [
            f"- **{s}**: {why}" for s, why in sorted(excluded.items())
        ]

    short = [cls for cls in TARGET_CLASSES if totals[cls] < MIN_TRAINABLE]
    lines += ["", f"## Classes under {MIN_TRAINABLE} images", ""]
    lines += [f"- `{cls}`: {totals[cls]}" for cls in short] or ["None."]

    if confirm:
        lines += ["", "## Mappings that need agronomist confirmation", ""]
        lines += [f'- {src} / "{label}": {note}' for (src, label), note in sorted(confirm.items())]

    lines += [
        "",
        "## Notes",
        "",
        "- Lab-style images (PlantVillage and similar plain-background sets) must never be in val or test:",
        "  they measure nothing about field photos. Sources marked `lab` are forced into train.",
        "- Look-alike groups (`field_id` PUB-…) never straddle splits; `split.csv` is what training reads.",
        "",
    ]
    return "\n".join(lines)


def run(external=EXTERNAL, out=OUT, mappings=MAPPINGS, test_sources=(), labels=None):
    ids = class_ids(labels or load_labels())
    candidates, excluded, confirm = [], {}, {}
    for source, config in SOURCES.items():
        extracted = Path(external) / source / "extracted"
        if not extracted.is_dir():
            continue
        if config.get("exclude"):
            excluded[source] = config["exclude"]
            continue
        mapping, needs = read_mapping_file(Path(mappings) / f"{source}.csv", ids)
        confirm.update({(source, label): note for label, note in needs.items()})
        found = discover(source, extracted, mapping)
        for c in found:
            if not c.dropped:
                inspect_image(c)
        candidates += found
        print(f"{source}: {len(found)} files", file=sys.stderr)

    drop_duplicates(candidates)
    kept = [c for c in candidates if not c.dropped and c.class_id]
    unmapped = [c for c in candidates if not c.dropped and not c.class_id]
    assign_group_codes(kept + unmapped)
    assign_splits(kept, test_sources)

    out = Path(out)
    if out.exists():
        shutil.rmtree(out)
    columns = template_columns()
    for subset, base in ((kept, out), (unmapped, out / "unmapped")):
        rows = []
        for c in subset:
            c.filename = f"{c.source}__{c.sha256[:12]}{c.path.suffix.lower().replace('.jpeg', '.jpg')}"
            folder = base / (c.class_id or Path(c.source) / c.original_label)
            folder.mkdir(parents=True, exist_ok=True)
            shutil.copy2(c.path, folder / c.filename)
            rows.append(metadata_row(c, columns))
        base.mkdir(parents=True, exist_ok=True)
        with (base / "metadata.csv").open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, columns)
            writer.writeheader()
            writer.writerows(sorted(rows, key=lambda r: r["filename"]))

    with (out / "split.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["filename", "field_id", "split"])
        writer.writerows(sorted((c.filename, c.group, c.split) for c in kept))

    # For train_baseline.py --mapping: each class folder is itself; unmapped/ is skipped.
    with (out / "training_mapping.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["source", "class_id"])
        writer.writerows(sorted((cls, cls) for cls in {c.class_id for c in kept}))
        writer.writerow(["unmapped", "skip"])

    (out / "report.md").write_text(
        report_markdown(candidates, excluded, confirm, test_sources), encoding="utf-8"
    )
    return candidates


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--test-source", action="append", default=[], choices=sorted(SOURCES))
    args = parser.parse_args(argv)
    candidates = run(test_sources=tuple(args.test_source))
    kept = sum(1 for c in candidates if not c.dropped and c.class_id)
    print(f"kept {kept}, dropped {sum(1 for c in candidates if c.dropped)}; see {OUT / 'report.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
