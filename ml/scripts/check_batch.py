"""Check a batch of field photos and its metadata.csv before it goes into the dataset (Build Step 3).

Usage:  python ml/scripts/check_batch.py ml/data/raw/2026-10-20_chongwe_el
        python ml/scripts/check_batch.py <batch> --raw-dir ml/data/raw   # also find copies in other batches

Prints one line per problem and exits 1 if there are errors, so a batch is only added (`dvc add`) when it's
clean. Warnings don't block. The columns and rules are in docs/ml/field-data.md (ADR 0012).
Standard library only, so it runs on any team laptop.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LABELS = ROOT / "ml" / "labels.json"

COLUMNS = [
    "filename",
    "crop",
    "suspected_class",
    "stage",
    "field_id",
    "farmer_code",
    "gps_lat",
    "gps_lng",
    "captured_at",
    "photographer",
    "zone",
    "notes",
]
REQUIRED = {"filename", "crop", "stage", "field_id", "farmer_code", "captured_at", "photographer", "zone"}
STAGES = {"none", "early", "mid", "advanced", "unknown"}
ZONES = {"I", "IIa", "IIb", "III"}  # Zambia's agro-ecological regions
CODE = re.compile(r"^[A-Z0-9][A-Z0-9-]{1,19}$")  # field_id, farmer_code: codes, never names or phone numbers
PHONE = re.compile(r"\d{9,}")
PHOTOGRAPHER = re.compile(r"^[A-Za-z]{2,4}$")  # initials
# Zambia's bounding box, with a little margin.
LAT_RANGE, LNG_RANGE = (-18.2, -8.1), (21.9, 33.8)
LUSAKA = timezone(timedelta(hours=2))  # Zambia has no daylight saving
EARLIEST = datetime(2026, 1, 1, tzinfo=LUSAKA)
DATE_FORMATS = ["%d/%m/%Y %H:%M", "%d/%m/%Y %H:%M:%S"]  # what spreadsheets in Zambia produce
MIN_SIDE, SMALL_SIDE = 224, 600  # model input; below SMALL_SIDE crops lose detail
HEIC_HELP = "HEIC photo (iPhone): set Settings > Camera > Formats > Most Compatible, and resend as JPEG"


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    classes: Counter = field(default_factory=Counter)
    rows: int = 0

    def error(self, where, message):
        self.errors.append(f"ERROR {where}: {message}")

    def warn(self, where, message):
        self.warnings.append(f"WARN  {where}: {message}")


def load_classes(path=LABELS):
    labels = json.loads(path.read_text(encoding="utf-8"))
    return {c["id"]: c for c in labels["classes"] if not c.get("retired")}


def jpeg_size(data):
    """(width, height) from a JPEG's start-of-frame segment, or None if it isn't a readable JPEG."""
    if data[:2] != b"\xff\xd8":
        return None
    pos = 2
    while pos + 4 <= len(data):
        if data[pos] != 0xFF:
            return None
        marker = data[pos + 1]
        if marker == 0xFF:  # fill byte
            pos += 1
            continue
        if marker in (0x01, *range(0xD0, 0xD8)):
            pos += 2
            continue
        length = int.from_bytes(data[pos + 2 : pos + 4], "big")
        if marker in range(0xC0, 0xD0) and marker not in (0xC4, 0xC8, 0xCC):
            if pos + 9 > len(data):
                return None
            height = int.from_bytes(data[pos + 5 : pos + 7], "big")
            width = int.from_bytes(data[pos + 7 : pos + 9], "big")
            return width, height
        if marker == 0xDA or length < 2:
            return None  # image data before any frame header
        pos += 2 + length
    return None


def parse_time(value):
    """ISO 8601 (`2026-10-20 14:03`, `2026-10-20T14:03+02:00`) or dd/mm/yyyy hh:mm. No zone means Lusaka."""
    try:
        moment = datetime.fromisoformat(value)
    except ValueError:
        for fmt in DATE_FORMATS:
            try:
                moment = datetime.strptime(value, fmt)
                break
            except ValueError:
                continue
        else:
            return None
    return moment if moment.tzinfo else moment.replace(tzinfo=LUSAKA)


def check_row(row, classes, report, where):
    crops = sorted({c["crop"] for c in classes.values()})
    for column in sorted(REQUIRED):
        if not row.get(column):
            report.error(where, f"{column} is empty")

    crop = row.get("crop", "")
    if crop and crop not in crops:
        report.error(where, f"crop {crop!r} is not one of {', '.join(crops)}")

    suspected = row.get("suspected_class", "")
    stage = row.get("stage", "")
    if suspected in ("", "unknown"):
        report.warn(where, "no suspected_class; it will need an expert label before training")
    elif suspected not in classes:
        report.error(where, f"suspected_class {suspected!r} is not a class id in ml/labels.json")
    else:
        cls = classes[suspected]
        if crop in crops and cls["crop"] != crop:
            report.error(where, f"suspected_class {suspected} is not a {crop} class")
        if cls["is_healthy"] and stage not in ("", "none"):
            report.error(where, "stage must be 'none' for a healthy leaf")
        if not cls["is_healthy"] and stage == "none":
            report.error(where, "stage 'none' is only for healthy leaves; use 'unknown' if unsure")
    if stage and stage not in STAGES:
        report.error(where, f"stage {stage!r} is not one of {', '.join(sorted(STAGES))}")
    report.classes[suspected or "unknown"] += 1

    for column in ("field_id", "farmer_code"):
        value = row.get(column, "")
        if value and not CODE.match(value):
            report.error(where, f"{column} {value!r} must be a code like LSK-014 (capitals, digits, '-')")
        elif PHONE.search(value):
            report.error(where, f"{column} must be a team code, not a phone number")
    photographer = row.get("photographer", "")
    if photographer and not PHOTOGRAPHER.match(photographer):
        report.error(where, f"photographer {photographer!r} should be initials, e.g. EL")
    zone = row.get("zone", "")
    if zone and zone not in ZONES:
        report.error(where, f"zone {zone!r} is not one of {', '.join(sorted(ZONES))}")

    lat, lng = row.get("gps_lat", ""), row.get("gps_lng", "")
    if bool(lat) != bool(lng):
        report.error(where, "give both gps_lat and gps_lng, or neither")
    elif lat:
        try:
            lat_f, lng_f = float(lat), float(lng)
        except ValueError:
            report.error(where, "gps_lat and gps_lng must be decimal degrees, e.g. -15.416 and 28.283")
        else:
            if not (LAT_RANGE[0] <= lat_f <= LAT_RANGE[1] and LNG_RANGE[0] <= lng_f <= LNG_RANGE[1]):
                report.error(where, f"GPS {lat}, {lng} is outside Zambia (latitude and longitude swapped?)")
    else:
        report.warn(where, "no GPS")

    captured = row.get("captured_at", "")
    if captured:
        moment = parse_time(captured)
        if moment is None:
            report.error(where, f"captured_at {captured!r}: use 2026-10-20 14:03 or 20/10/2026 14:03")
        elif not EARLIEST <= moment <= datetime.now(UTC) + timedelta(days=1):
            report.error(where, f"captured_at {captured} is before 2026 or in the future (camera clock?)")


def check_image(path, report, where):
    data = path.read_bytes()
    if not data:
        report.error(where, "the file is empty")
        return None
    if data[4:12] in (b"ftypheic", b"ftypheix", b"ftypmif1"):
        report.error(where, HEIC_HELP)
        return None
    size = jpeg_size(data)
    if size is None:
        report.error(where, "not a readable JPEG")
    elif min(size) < MIN_SIDE:
        report.error(where, f"{size[0]}x{size[1]} is smaller than the model's {MIN_SIDE} px input")
    elif min(size) < SMALL_SIDE:
        report.warn(where, f"only {size[0]}x{size[1]}; use the camera's full resolution")
    return hashlib.sha256(data).hexdigest()


def known_hashes(raw_dir, batch):
    """sha256 -> path for every photo in the other batches under raw_dir."""
    hashes = {}
    for path in raw_dir.glob("*/*"):
        if path.parent.resolve() != batch.resolve() and path.suffix.lower() in (".jpg", ".jpeg"):
            hashes[hashlib.sha256(path.read_bytes()).hexdigest()] = path
    return hashes


def check_batch(batch, classes, raw_dir=None):
    report = Report()
    csv_path = batch / "metadata.csv"
    if not csv_path.is_file():
        report.error(batch.name, "no metadata.csv in the batch folder")
        return report
    try:
        with csv_path.open(encoding="utf-8-sig", newline="") as f:  # -sig: Excel adds a BOM
            reader = csv.DictReader(f)
            header = reader.fieldnames or []
            rows = [{k: (v or "").strip() for k, v in row.items() if k} for row in reader]
    except UnicodeDecodeError:
        report.error("metadata.csv", "not UTF-8; in Excel use Save As > CSV UTF-8")
        return report
    missing = [c for c in COLUMNS if c not in header]
    extra = [c for c in header if c not in COLUMNS]
    if missing:
        report.error("metadata.csv", f"missing columns: {', '.join(missing)}")
        return report
    if extra:
        report.warn("metadata.csv", f"unknown columns, ignored: {', '.join(extra)}")

    seen = known_hashes(raw_dir, batch) if raw_dir else {}
    names, farmer_of_field = Counter(), {}
    listed = set()
    for number, row in enumerate(rows, start=2):  # row 1 is the header
        name = row.get("filename", "")
        where = f"row {number} ({name or 'no filename'})"
        report.rows += 1
        check_row(row, classes, report, where)
        if not name:
            continue
        names[name] += 1
        if names[name] == 2:
            report.error(where, "filename listed twice")
        listed.add(name.lower())

        field_id, farmer = row.get("field_id"), row.get("farmer_code")
        if field_id and farmer:
            if farmer_of_field.setdefault(field_id, farmer) != farmer:
                first = farmer_of_field[field_id]
                report.error(where, f"field {field_id} is listed under farmers {first} and {farmer}")

        path = batch / name
        if "/" in name or "\\" in name or not path.is_file():
            report.error(where, "no such file in the batch folder")
            continue
        if path.suffix.lower() in (".heic", ".heif"):
            report.error(where, HEIC_HELP)
            continue
        if path.suffix.lower() not in (".jpg", ".jpeg"):
            report.error(where, "only .jpg / .jpeg photos")
            continue
        digest = check_image(path, report, where)
        if digest in seen:
            report.error(where, f"same photo as {seen[digest].parent.name}/{seen[digest].name}")
        elif digest:
            seen[digest] = path

    for path in sorted(batch.iterdir()):
        if path.is_file() and path.name != "metadata.csv" and path.name.lower() not in listed:
            report.error(path.name, "photo is not listed in metadata.csv")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("batch", type=Path, help="folder with the photos and metadata.csv")
    parser.add_argument("--raw-dir", type=Path, help="look for duplicate photos in the other batches here")
    args = parser.parse_args(argv)

    report = check_batch(args.batch, load_classes(), args.raw_dir)
    for line in report.errors + report.warnings:
        print(line)
    counts = f"{report.rows} rows, {len(report.errors)} errors, {len(report.warnings)} warnings"
    print(f"\n{args.batch.name}: {counts}")
    for class_id, count in sorted(report.classes.items()):
        print(f"  {count:5d}  {class_id}")
    return 1 if report.errors else 0


if __name__ == "__main__":
    sys.exit(main())
