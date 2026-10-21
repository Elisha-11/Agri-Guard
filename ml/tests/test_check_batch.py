import csv
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from check_batch import COLUMNS, check_batch, jpeg_size, load_classes, main, parse_time  # noqa: E402

CLASSES = load_classes()


def jpeg(width=1200, height=900, extra=b""):
    """A minimal JPEG with a frame header: enough for the checks, which don't decode pixels."""
    frame = b"\xff\xc0\x00\x11\x08" + height.to_bytes(2, "big") + width.to_bytes(2, "big") + bytes(10)
    return b"\xff\xd8\xff\xe0\x00\x04JF" + frame + b"\xff\xda\x00\x02" + extra + b"\xff\xd9"


GOOD = {
    "filename": "IMG_0001.jpg",
    "crop": "maize",
    "suspected_class": "maize__grey_leaf_spot",
    "stage": "mid",
    "field_id": "CHG-001",
    "farmer_code": "F-0007",
    "gps_lat": "-15.416",
    "gps_lng": "28.283",
    "captured_at": "2026-10-20 14:03",
    "photographer": "EL",
    "zone": "IIa",
    "notes": "",
}


def make_batch(tmp_path, rows, name="2026-10-20_chongwe_el", photos=None):
    batch = tmp_path / name
    batch.mkdir()
    with (batch / "metadata.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    for row in rows:
        if row.get("filename"):
            (batch / row["filename"]).write_bytes(
                (photos or {}).get(row["filename"], jpeg(extra=row["filename"].encode()))
            )
    return batch


def row(**overrides):
    return {**GOOD, **overrides}


def errors(tmp_path, *rows, **kwargs):
    return check_batch(make_batch(tmp_path, list(rows), **kwargs), CLASSES).errors


def test_a_clean_batch_has_no_errors_or_warnings(tmp_path):
    report = check_batch(make_batch(tmp_path, [row(), row(filename="IMG_0002.jpg")]), CLASSES)
    assert report.errors == [] and report.warnings == []
    assert report.rows == 2 and report.classes["maize__grey_leaf_spot"] == 2


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"crop": "maiz"}, "crop 'maiz' is not one of"),
        ({"suspected_class": "maize__alien_blight"}, "not a class id"),
        ({"suspected_class": "cassava__healthy", "stage": "none"}, "not a maize class"),
        ({"suspected_class": "maize__healthy", "stage": "early"}, "'none' for a healthy leaf"),
        ({"stage": "none"}, "only for healthy leaves"),
        ({"stage": "late"}, "stage 'late' is not one of"),
        ({"field_id": ""}, "field_id is empty"),
        ({"farmer_code": "Mary Banda"}, "must be a code"),
        ({"farmer_code": "0971234567"}, "not a phone number"),
        ({"photographer": "Elisha"}, "should be initials"),
        ({"zone": "2a"}, "zone '2a' is not one of"),
        ({"gps_lng": ""}, "both gps_lat and gps_lng"),
        ({"gps_lat": "28.283", "gps_lng": "-15.416"}, "outside Zambia"),
        ({"gps_lat": "15°24'S"}, "decimal degrees"),
        ({"captured_at": "yesterday"}, "use 2026-10-20 14:03"),
        ({"captured_at": "2019-01-01 08:00"}, "before 2026 or in the future"),
    ],
)
def test_bad_metadata_is_an_error(tmp_path, overrides, message):
    found = errors(tmp_path, row(**overrides))
    assert any(message in e for e in found), found


def test_unsure_class_is_a_warning_not_an_error(tmp_path):
    report = check_batch(make_batch(tmp_path, [row(suspected_class="", stage="unknown")]), CLASSES)
    assert report.errors == []
    assert any("expert label" in w for w in report.warnings)


def test_no_gps_is_a_warning(tmp_path):
    report = check_batch(make_batch(tmp_path, [row(gps_lat="", gps_lng="")]), CLASSES)
    assert report.errors == [] and any("no GPS" in w for w in report.warnings)


def test_spreadsheet_dates_are_read_as_day_first_lusaka_time():
    moment = parse_time("03/11/2026 09:30")
    assert (moment.day, moment.month) == (3, 11)
    assert moment.utcoffset().total_seconds() == 2 * 3600


def test_a_field_belongs_to_one_farmer(tmp_path):
    found = errors(tmp_path, row(), row(filename="IMG_0002.jpg", farmer_code="F-0099"))
    assert any("listed under farmers F-0007 and F-0099" in e for e in found)


class TestFiles:
    def test_missing_photo(self, tmp_path):
        batch = make_batch(tmp_path, [row()])
        (batch / "IMG_0001.jpg").unlink()
        assert any("no such file" in e for e in check_batch(batch, CLASSES).errors)

    def test_photo_not_in_the_csv(self, tmp_path):
        batch = make_batch(tmp_path, [row()])
        (batch / "IMG_0099.jpg").write_bytes(jpeg())
        assert any("IMG_0099.jpg: photo is not listed" in e for e in check_batch(batch, CLASSES).errors)

    def test_listed_twice(self, tmp_path):
        assert any("listed twice" in e for e in errors(tmp_path, row(), row()))

    def test_same_photo_under_two_names(self, tmp_path):
        same = jpeg()
        found = errors(
            tmp_path,
            row(),
            row(filename="IMG_0002.jpg"),
            photos={"IMG_0001.jpg": same, "IMG_0002.jpg": same},
        )
        assert any("same photo as" in e for e in found)

    def test_same_photo_in_an_earlier_batch(self, tmp_path):
        make_batch(tmp_path, [row()], name="2026-10-19_kafue_rn", photos={"IMG_0001.jpg": jpeg()})
        batch = make_batch(tmp_path, [row()], photos={"IMG_0001.jpg": jpeg()})
        found = check_batch(batch, CLASSES, raw_dir=tmp_path).errors
        assert any("same photo as 2026-10-19_kafue_rn/IMG_0001.jpg" in e for e in found)

    def test_heic_from_an_iphone(self, tmp_path):
        heic = b"\x00\x00\x00\x18ftypheic" + bytes(20)
        found = errors(tmp_path, row(), photos={"IMG_0001.jpg": heic})
        assert any("Most Compatible" in e for e in found)

    @pytest.mark.parametrize(
        "photo, message",
        [(b"", "empty"), (b"not a jpeg", "not a readable JPEG"), (jpeg(200, 150), "smaller than")],
    )
    def test_unusable_photo(self, tmp_path, photo, message):
        assert any(message in e for e in errors(tmp_path, row(), photos={"IMG_0001.jpg": photo}))

    def test_small_photo_is_a_warning(self, tmp_path):
        report = check_batch(make_batch(tmp_path, [row()], photos={"IMG_0001.jpg": jpeg(640, 480)}), CLASSES)
        assert report.errors == [] and any("full resolution" in w for w in report.warnings)


class TestCsv:
    def test_no_metadata_csv(self, tmp_path):
        (tmp_path / "batch").mkdir()
        assert "no metadata.csv" in check_batch(tmp_path / "batch", CLASSES).errors[0]

    def test_missing_column(self, tmp_path):
        batch = tmp_path / "batch"
        batch.mkdir()
        (batch / "metadata.csv").write_text("filename,crop\nIMG_0001.jpg,maize\n", encoding="utf-8")
        assert "missing columns: suspected_class" in check_batch(batch, CLASSES).errors[0]

    def test_excel_bom_is_fine(self, tmp_path):
        batch = make_batch(tmp_path, [row()])
        csv_path = batch / "metadata.csv"
        csv_path.write_bytes(b"\xef\xbb\xbf" + csv_path.read_bytes())
        assert check_batch(batch, CLASSES).errors == []

    def test_not_utf8(self, tmp_path):
        batch = make_batch(tmp_path, [row(notes="café")])
        csv_path = batch / "metadata.csv"
        csv_path.write_bytes(csv_path.read_text(encoding="utf-8").encode("cp1252"))
        assert "CSV UTF-8" in check_batch(batch, CLASSES).errors[0]


def test_jpeg_size_reads_the_frame_header():
    assert jpeg_size(jpeg(4000, 3000)) == (4000, 3000)
    assert jpeg_size(b"\xff\xd8\xff\xda\x00\x02\xff\xd9") is None


def test_exit_code(tmp_path, capsys):
    assert main([str(make_batch(tmp_path, [row()]))]) == 0
    assert main([str(make_batch(tmp_path, [row(crop="rice")], name="bad"))]) == 1
    assert "1 errors" in capsys.readouterr().out
