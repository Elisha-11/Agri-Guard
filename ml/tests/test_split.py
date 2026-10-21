import csv
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from split import SPLITS, assign, field_conflicts, main  # noqa: E402
from test_check_batch import GOOD, make_batch  # noqa: E402

CLASSES = ["maize__healthy", "maize__grey_leaf_spot", "maize__common_rust"]


def photos_for(farmers, per_class=10):
    """`farmers` farmers, each with `per_class` photos of every class in CLASSES."""
    return [
        {"farmer_code": f"F-{n:04d}", "field_id": f"FLD-{n:03d}", "suspected_class": c}
        for n in range(farmers)
        for c in CLASSES
        for _ in range(per_class)
    ]


def split_of_each_photo(photos, assignment):
    return Counter(assignment[p["farmer_code"]] for p in photos)


class TestAssign:
    def test_ratios_are_close_to_target_with_many_farmers(self):
        photos = photos_for(40)
        assignment, current = assign(photos, {}, [0.7, 0.15, 0.15])
        shares = {s: sum(current[s].values()) / len(photos) for s in SPLITS}
        assert abs(shares["train"] - 0.7) < 0.05
        assert abs(shares["val"] - 0.15) < 0.05 and abs(shares["test"] - 0.15) < 0.05

    def test_every_class_reaches_every_split(self):
        photos = [
            {"farmer_code": f"F-{n:04d}", "suspected_class": CLASSES[n % 3]}
            for n in range(60)
            for _ in range(5)
        ]
        _, current = assign(photos, {}, [0.7, 0.15, 0.15])
        for split in SPLITS:
            assert all(current[split][c] > 0 for c in CLASSES), (split, current[split])

    def test_existing_farmers_never_move(self):
        photos = photos_for(20)
        first, _ = assign(photos, {}, [0.7, 0.15, 0.15])
        more = photos + photos_for(30, per_class=3)[20 * 3 * 3 :]  # farmers 20-29 are new
        second, _ = assign(more, first, [0.7, 0.15, 0.15])
        assert all(second[f] == s for f, s in first.items())
        assert len(second) == 30

    def test_a_farmers_new_photos_follow_their_split(self):
        """Even if adding them unbalances the split: keeping farmers apart matters more than ratios."""
        existing = {"F-0000": "test"}
        photos = photos_for(1, per_class=100)
        assignment, current = assign(photos, existing, [0.7, 0.15, 0.15])
        assert assignment == existing and sum(current["test"].values()) == 300

    def test_the_same_input_gives_the_same_split(self):
        photos = photos_for(25)
        assert assign(photos, {}, [0.7, 0.15, 0.15]) == assign(list(reversed(photos)), {}, [0.7, 0.15, 0.15])

    def test_unlabelled_photos_are_split_too(self):
        photos = photos_for(10) + [{"farmer_code": "F-0099", "suspected_class": ""}] * 5
        assignment, _ = assign(photos, {}, [0.7, 0.15, 0.15])
        assert "F-0099" in assignment


def test_field_under_two_farmers_across_batches():
    photos = [
        {"field_id": "CHG-001", "farmer_code": "F-0001"},
        {"field_id": "CHG-001", "farmer_code": "F-0002"},
    ]
    assert field_conflicts(photos) == ["CHG-001: F-0001, F-0002"]


class TestMain:
    def rows(self, batch_no, farmers):
        return [
            {
                **GOOD,
                "filename": f"IMG_{batch_no}_{n}.jpg",
                "farmer_code": f,
                "field_id": f"FLD-{f[2:]}",
            }
            for n, f in enumerate(farmers)
        ]

    def run(self, tmp_path):
        args = ["--raw-dir", str(tmp_path / "raw"), "--assignments", str(tmp_path / "farmers.csv")]
        return main([*args, "--out", str(tmp_path / "split.csv")])

    def read(self, path):
        with path.open(encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))

    def test_writes_assignments_and_the_photo_list(self, tmp_path, capsys):
        raw = tmp_path / "raw"
        raw.mkdir()
        make_batch(raw, self.rows(1, [f"F-{n:04d}" for n in range(10)]), name="2026-10-19_kafue_rn")
        assert self.run(tmp_path) == 0

        farmers = {r["farmer_code"]: r["split"] for r in self.read(tmp_path / "farmers.csv")}
        photos = self.read(tmp_path / "split.csv")
        assert len(farmers) == 10 and len(photos) == 10
        assert all(p["split"] == farmers[p["farmer_code"]] for p in photos)
        assert photos[0]["batch"] == "2026-10-19_kafue_rn"
        assert "10 photos, 10 farmers (10 new)" in capsys.readouterr().out

    def test_rerun_after_a_new_batch_keeps_old_farmers(self, tmp_path):
        raw = tmp_path / "raw"
        raw.mkdir()
        make_batch(raw, self.rows(1, [f"F-{n:04d}" for n in range(10)]), name="b1")
        self.run(tmp_path)
        before = self.read(tmp_path / "farmers.csv")
        make_batch(raw, self.rows(2, [f"F-{n:04d}" for n in range(5, 15)]), name="b2")
        assert self.run(tmp_path) == 0
        after = {r["farmer_code"]: r["split"] for r in self.read(tmp_path / "farmers.csv")}
        assert all(after[r["farmer_code"]] == r["split"] for r in before)
        assert len(after) == 15

    def test_refuses_a_batch_with_errors(self, tmp_path, capsys):
        raw = tmp_path / "raw"
        raw.mkdir()
        make_batch(raw, [{**self.rows(1, ["F-0001"])[0], "crop": "rice"}], name="bad")
        assert self.run(tmp_path) == 1
        assert "bad" in capsys.readouterr().out
        assert not (tmp_path / "farmers.csv").exists()

    def test_refuses_a_field_under_two_farmers_across_batches(self, tmp_path, capsys):
        raw = tmp_path / "raw"
        raw.mkdir()
        make_batch(raw, [{**GOOD, "field_id": "CHG-001", "farmer_code": "F-0001"}], name="b1")
        make_batch(
            raw,
            [{**GOOD, "filename": "IMG_2.jpg", "field_id": "CHG-001", "farmer_code": "F-0002"}],
            name="b2",
        )
        assert self.run(tmp_path) == 1
        assert "CHG-001: F-0001, F-0002" in capsys.readouterr().out
