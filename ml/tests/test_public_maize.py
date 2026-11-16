"""Public maize dataset pipeline: mapping, augmentation filter, duplicate clustering, grouping, splits, rows.

The decision logic is standard library and runs in CI. The end-to-end test needs Pillow (ml/requirements.txt)
to write and read real JPEGs, and skips without it.
"""

import csv
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import public_maize as pm  # noqa: E402
from dataset import DatasetError, class_ids, load_labels, parse_mapping  # noqa: E402

IDS = class_ids(load_labels())
MAPPINGS = Path(__file__).resolve().parents[1] / "mappings"


def cand(
    source="karaagro", rel="healthy_01/a.jpg", label="healthy", cls="maize__healthy", dhash=0, sha="x", **kw
):
    c = pm.Candidate(source, Path(rel), rel, label, cls, sha256=sha, dhash=dhash, **kw)
    return c


# --- mapping files ------------------------------------------------------------------------------------------


@pytest.mark.parametrize("path", sorted(MAPPINGS.glob("*.csv")), ids=lambda p: p.stem)
def test_every_mapping_file_parses_and_targets_real_maize_classes(path):
    mapping, _ = pm.read_mapping_file(path, IDS)
    for label, target in mapping.items():
        assert target is None or target.startswith("maize__"), (label, target)


def test_unclear_labels_are_flagged_or_left_unmapped_never_guessed():
    mapping, confirm = pm.read_mapping_file(MAPPINGS / "ghana_mendeley.csv", IDS)
    assert "leaf blight" in confirm and "leaf spot" in confirm
    assert mapping["fall armyworm"] is None
    assert mapping["grasshopper"] is None


def test_fall_armyworm_is_not_a_class():
    for path in MAPPINGS.glob("*.csv"):
        mapping, _ = pm.read_mapping_file(path, IDS)
        assert all(
            target is None for label, target in mapping.items() if "faw" in label or "armyworm" in label
        )


def test_a_mapping_to_an_unknown_class_is_rejected(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("source,class_id,confirm,note\nrust,maize__rust,,\n", encoding="utf-8")
    with pytest.raises(DatasetError, match="maize__rust"):
        parse_mapping(bad, IDS)


# --- augmentation filter ------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "rel",
    [
        "augmented/healthy/a.jpg",
        "train/aug_0001.jpg",
        "x/img_rot90.jpg",
        "x/leaf-flipped.png",
        "x/a_bright.jpg",
    ],
)
def test_augmented_copies_are_recognised(rel):
    assert pm.AUGMENTED.search(rel)


def test_roboflow_exports_of_one_photo_keep_only_the_first(tmp_path):
    folder = tmp_path / "healthy_01" / "healthy_01"
    folder.mkdir(parents=True)
    names = [
        "0057C9C9-16_59_30_jpeg.rf.016f84c06c8647650d43e8122104182b.jpg",
        "0057C9C9-16_59_30_jpeg.rf.9a1b2c3d4e5f60718293a4b5c6d7e8f9.jpg",  # same photo, second export
        "1A2B3C4D-17_01_02_jpeg.rf.aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.jpg",
    ]
    for name in names:
        (folder / name).write_bytes(b"x")
    found = pm.discover("karaagro", tmp_path, {"healthy": "maize__healthy"})
    assert [c.dropped for c in found] == ["", "augmented (second Roboflow export of one photo)", ""]
    assert pm.original_photo(folder / names[0]) == "0057C9C9-16_59_30_jpeg"
    assert pm.original_photo(Path("DSC_0001.JPG")) == "DSC_0001"


@pytest.mark.parametrize(
    "rel", ["healthy_01/IMG_0001.jpg", "MSV/MSV_123.jpg", "x/DSC_4410.JPG", "crops/x.jpg"]
)
def test_ordinary_names_are_not_mistaken_for_augmentation(rel):
    assert not pm.AUGMENTED.search(rel)


# --- hashing and duplicates ---------------------------------------------------------------------------------


def test_dhash_compares_neighbouring_pixels():
    rising = [col for _row in range(8) for col in range(9)]  # every left < right
    assert pm.dhash_bits(rising) == 0
    falling = [9 - col for _row in range(8) for col in range(9)]
    assert pm.dhash_bits(falling) == (1 << 64) - 1


def test_near_pairs_finds_exactly_the_pairs_within_distance():
    a = 0
    b = 0b111  # 3 bits from a
    c = (1 << 64) - 1  # far from both
    d = 0b11111  # 5 bits from a, 2 from b
    assert pm.near_pairs([a, b, c, d], 4) == [(0, 1), (1, 3)]
    assert pm.near_pairs([a, b, c, d], 5) == [(0, 1), (0, 3), (1, 3)]


def test_exact_and_near_duplicates_are_dropped_keeping_the_higher_priority_source():
    kara = cand("karaagro", "healthy_01/a.jpg", sha="same", dhash=0)
    tz_exact = cand("tanzania", "HEALTHY/b.jpg", label="HEALTHY", sha="same", dhash=0)
    tz_near = cand("tanzania", "HEALTHY/c.jpg", label="HEALTHY", sha="other", dhash=0b11)
    unrelated = cand("tanzania", "HEALTHY/d.jpg", label="HEALTHY", sha="d", dhash=(1 << 64) - 1)
    pm.drop_duplicates([tz_exact, tz_near, unrelated, kara])

    assert kara.dropped == ""
    assert tz_exact.dropped == "exact duplicate" and tz_exact.duplicate_of == "karaagro:healthy_01/a.jpg"
    assert tz_near.dropped == "near duplicate" and tz_near.duplicate_of == "karaagro:healthy_01/a.jpg"
    assert unrelated.dropped == ""


def test_already_dropped_images_are_ignored_by_duplicate_detection():
    corrupt = cand(rel="healthy_01/x.jpg", sha="s", dropped="corrupt")
    good = cand(rel="healthy_01/y.jpg", sha="s")
    pm.drop_duplicates([corrupt, good])
    assert good.dropped == ""


# --- grouping and splits ------------------------------------------------------------------------------------


def test_look_alikes_share_a_group_code_in_check_batch_format():
    import re

    items = [cand(rel=f"h/{i}.jpg", dhash=h) for i, h in enumerate([0, 0b1111_1111, (1 << 64) - 1])]
    pm.assign_group_codes(items)
    assert items[0].group == items[1].group != items[2].group
    assert all(re.fullmatch(r"[A-Z0-9][A-Z0-9-]{1,19}", c.group) for c in items)


def _many(n, source="karaagro", cls="maize__healthy", start=0):
    # far-apart hashes so each image is its own group
    return [
        cand(source, f"x/{start + i}.jpg", cls=cls, dhash=(start + i) * 0x9E3779B97F4A7C15 % (1 << 64))
        for i in range(n)
    ]


def test_groups_never_straddle_splits():
    items = _many(40) + _many(40, cls="maize__streak_virus", start=100)
    twins = [cand(rel="x/t1.jpg", dhash=12345), cand(rel="x/t2.jpg", dhash=12345 ^ 0b1)]
    items += twins
    pm.assign_group_codes(items)
    pm.assign_splits(items)
    assert twins[0].split == twins[1].split
    assert {c.split for c in items} == set(pm.SPLITS)


def test_a_held_out_source_is_the_whole_test_set(monkeypatch):
    monkeypatch.setitem(pm.SOURCES, "zmld", {**pm.SOURCES["zmld"], "exclude": ""})
    items = _many(30) + _many(10, source="zmld", start=500)
    pm.assign_group_codes(items)
    pm.assign_splits(items, test_sources=("zmld",))
    assert {c.split for c in items if c.source == "zmld"} == {"test"}
    assert {c.split for c in items if c.source != "zmld"} <= {"train", "val"}


def test_lab_style_images_are_never_in_val_or_test(monkeypatch):
    monkeypatch.setitem(pm.SOURCES, "plantvillage", {"priority": 9, "licence": "x", "lab": True})
    items = _many(30) + _many(30, source="plantvillage", start=300)
    pm.assign_group_codes(items)
    pm.assign_splits(items)
    assert {c.split for c in items if c.source == "plantvillage"} == {"train"}


def test_a_lab_image_pulls_its_whole_look_alike_group_into_train(monkeypatch):
    monkeypatch.setitem(pm.SOURCES, "plantvillage", {"priority": 9, "licence": "x", "lab": True})
    field_photo = cand(rel="x/field.jpg", dhash=777)
    lab_copy = cand("plantvillage", "x/lab.jpg", dhash=777 ^ 0b11)
    items = [field_photo, lab_copy] + _many(20)
    pm.assign_group_codes(items)
    pm.assign_splits(items)
    assert field_photo.split == lab_copy.split == "train"


# --- metadata and report ------------------------------------------------------------------------------------


def test_metadata_rows_use_the_template_columns_plus_source_licence_and_label():
    columns = pm.template_columns()
    with pm.TEMPLATE.open(encoding="utf-8") as f:
        template = next(csv.reader(f))
    assert columns == template + ["source", "licence", "original_label"]

    c = cand(
        rel="healthy_01/IMG_1.jpg",
        group="PUB-000001",
        filename="karaagro__abc.jpg",
        captured_at="2021-06-01 10:00",
    )
    row = pm.metadata_row(c, columns)
    assert list(row) == columns
    assert row["suspected_class"] == "maize__healthy" and row["stage"] == "unknown"
    assert row["field_id"] == "PUB-000001" and row["farmer_code"] == ""
    assert row["gps_lat"] == row["gps_lng"] == "" and row["zone"] == ""
    assert row["licence"] == "CC0-1.0" and row["original_label"] == "healthy"
    assert "healthy_01/IMG_1.jpg" in row["notes"]


def test_report_lists_short_classes_drop_reasons_and_confirmations():
    kept = _many(5)
    for c in kept:
        c.split = "train"
    dropped = [cand(rel="x/bad.jpg", dropped="corrupt"), cand(rel="x/aug.jpg", dropped="augmented")]
    text = pm.report_markdown(
        kept + dropped,
        excluded={"zmld": "broken upload"},
        confirm={("ghana_mendeley", "leaf spot"): "may not be GLS"},
        test_sources=(),
    )
    assert "| `maize__healthy` |" in text and "**5**" in text
    assert "| karaagro | corrupt | 1 |" in text and "| karaagro | augmented | 1 |" in text
    assert "`maize__common_rust`: 0" in text
    assert "zmld**: broken upload" in text
    assert 'ghana_mendeley / "leaf spot"' in text
    assert "never be in val or test" in text


# --- end to end with real JPEGs -----------------------------------------------------------------------------


def test_end_to_end_on_tiny_jpegs(tmp_path):
    Image = pytest.importorskip("PIL.Image")
    import random

    def photo(path, seed, size=(300, 260)):
        rng = random.Random(seed)
        img = Image.new("RGB", (6, 6))
        img.putdata([tuple(rng.randrange(256) for _ in range(3)) for _ in range(36)])
        path.parent.mkdir(parents=True, exist_ok=True)
        img.resize(size, Image.Resampling.NEAREST).save(path, "JPEG", quality=95)

    ext = tmp_path / "external" / "karaagro" / "extracted"
    for i in range(12):
        photo(ext / "healthy_01" / f"h{i}.jpg", i)
        photo(ext / "maize_streak_01" / f"s{i}.jpg", 100 + i)
    photo(ext / "faw_01" / "f0.jpg", 200)
    photo(ext / "healthy_01" / "tiny.jpg", 300, size=(100, 100))
    photo(ext / "healthy_01" / "h0_aug.jpg", 0)
    (ext / "healthy_01" / "broken.jpg").write_bytes(b"not a jpeg")
    (ext / "healthy_01" / "h0_copy.jpg").write_bytes((ext / "healthy_01" / "h0.jpg").read_bytes())

    out = tmp_path / "out"
    candidates = pm.run(external=tmp_path / "external", out=out)
    reasons = {c.path.name: c.dropped for c in candidates}
    assert reasons["tiny.jpg"] == "under 224 px"
    assert reasons["broken.jpg"] == "corrupt"
    assert reasons["h0_aug.jpg"] == "augmented"
    assert "duplicate" in reasons["h0_copy.jpg"] or "duplicate" in reasons["h0.jpg"]

    rows = list(csv.DictReader((out / "metadata.csv").open(encoding="utf-8")))
    assert len(rows) == 24
    assert {r["suspected_class"] for r in rows} == {"maize__healthy", "maize__streak_virus"}
    for r in rows:
        assert (out / r["suspected_class"] / r["filename"]).is_file()

    unmapped = list(csv.DictReader((out / "unmapped" / "metadata.csv").open(encoding="utf-8")))
    assert [r["original_label"] for r in unmapped] == ["faw"]
    assert (out / "unmapped" / "karaagro" / "faw").is_dir()

    splits = list(csv.DictReader((out / "split.csv").open(encoding="utf-8")))
    assert {s["filename"] for s in splits} == {r["filename"] for r in rows}
    assert {s["split"] for s in splits} <= set(pm.SPLITS)

    mapping = (out / "training_mapping.csv").read_text(encoding="utf-8")
    assert "unmapped,skip" in mapping
    report = (out / "report.md").read_text(encoding="utf-8")
    assert "maize__lethal_necrosis`: 0" in report
