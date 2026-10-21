"""Dataset logic for baseline training: mapping, scan, splits, weights, metrics, run config. No TensorFlow."""

import csv
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from dataset import (  # noqa: E402
    DatasetError,
    Item,
    check_output_order,
    class_ids,
    class_weights,
    confusion_matrix,
    grouped_split,
    load_labels,
    parse_mapping,
    per_class_metrics,
    read_metadata,
    run_config,
    scan_images,
    smoke_sample,
    split_counts,
    stratified_split,
    summary_metrics,
    write_confusion_csv,
    write_metrics_csv,
)

LABELS = load_labels()
IDS = class_ids(LABELS)


def write(path, text):
    path.write_text(text, encoding="utf-8")
    return path


def image_tree(root, folders):
    """{folder: n} -> root/folder/0.jpg ... (empty files; the scan only looks at names)."""
    for folder, n in folders.items():
        (root / folder).mkdir(parents=True)
        for k in range(n):
            (root / folder / f"{k}.jpg").write_bytes(b"")
    return root


class TestLabels:
    def test_ids_are_in_index_order(self):
        assert IDS[0] == "maize__healthy" and len(IDS) == 19

    def test_out_of_order_labels_are_rejected(self):
        labels = {"classes": [{"index": 1, "id": "a"}, {"index": 0, "id": "b"}]}
        with pytest.raises(DatasetError, match="0..N-1"):
            class_ids(labels)

    def test_output_order_check(self):
        assert check_output_order(IDS, LABELS) == []
        swapped = [IDS[1], IDS[0], *IDS[2:]]
        assert check_output_order(swapped, LABELS) == [
            f"output 0 is {IDS[1]!r}, labels.json says {IDS[0]!r}",
            f"output 1 is {IDS[0]!r}, labels.json says {IDS[1]!r}",
        ]
        assert "18 outputs" in check_output_order(IDS[:-1], LABELS)[0]


class TestMapping:
    def test_many_to_one_and_skip(self, tmp_path):
        path = write(
            tmp_path / "m.csv",
            "source,class_id\nCorn___Common_rust,maize__common_rust\nrust_extra,maize__common_rust\n"
            "Tomato___healthy,\nPotato___blight,skip\n",
        )
        assert parse_mapping(path, set(IDS)) == {
            "Corn___Common_rust": "maize__common_rust",
            "rust_extra": "maize__common_rust",
            "Tomato___healthy": None,
            "Potato___blight": None,
        }

    def test_every_problem_is_reported(self, tmp_path):
        path = write(
            tmp_path / "m.csv",
            "source,class_id\na,maize__alien\n,maize__healthy\nb,maize__healthy\nb,maize__common_rust\n",
        )
        with pytest.raises(DatasetError) as exc:
            parse_mapping(path, set(IDS))
        assert len(exc.value.problems) == 3
        assert "'maize__alien' is not a class id" in exc.value.problems[0]

    def test_needs_both_columns(self, tmp_path):
        with pytest.raises(DatasetError, match="source,class_id"):
            parse_mapping(write(tmp_path / "m.csv", "folder,label\n"), set(IDS))


class TestScan:
    def test_labels_skips_and_reports_empty_classes(self, tmp_path):
        root = image_tree(tmp_path / "img", {"rust": 3, "healthy": 2, "tomato": 4})
        (root / "rust" / "notes.txt").write_text("x")
        scan = scan_images(
            root, {"rust": "maize__common_rust", "healthy": "maize__healthy", "tomato": None}, IDS
        )
        assert Counter(i.class_id for i in scan.items) == {"maize__common_rust": 3, "maize__healthy": 2}
        assert scan.items[0].path == "healthy/0.jpg"
        assert scan.skipped == {"tomato": 4}
        assert len(scan.empty) == 17 and scan.empty[0] == "maize__northern_leaf_blight"

    def test_unmapped_folder_is_an_error(self, tmp_path):
        root = image_tree(tmp_path / "img", {"rust": 1, "mystery": 1})
        with pytest.raises(DatasetError, match="'mystery' is not in the mapping"):
            scan_images(root, {"rust": "maize__common_rust"}, IDS)


def items(per_class):
    return [Item(f"{c}/{k}.jpg", c) for c, n in per_class.items() for k in range(n)]


class TestStratifiedSplit:
    def test_ratios_no_overlap_and_deterministic(self):
        data = items({"maize__healthy": 100, "maize__common_rust": 40})
        stratified_split(data, seed=7)
        counts = split_counts(data, IDS)
        assert counts["maize__healthy"] == {"train": 70, "val": 15, "test": 15}
        assert counts["maize__common_rust"] == {"train": 28, "val": 6, "test": 6}
        again = items({"maize__healthy": 100, "maize__common_rust": 40})[::-1]
        stratified_split(again, seed=7)
        assert {i.path: i.split for i in data} == {i.path: i.split for i in again}

    def test_small_class_still_reaches_val_and_test(self):
        data = items({"maize__streak_virus": 3})
        stratified_split(data)
        assert sorted(i.split for i in data) == ["test", "train", "val"]

    def test_seed_changes_the_split(self):
        a, b = items({"maize__healthy": 50}), items({"maize__healthy": 50})
        stratified_split(a, seed=1)
        stratified_split(b, seed=2)
        assert [i.split for i in a] != [i.split for i in b]


def metadata_file(tmp_path, rows, columns):
    path = tmp_path / "meta.csv"
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    return read_metadata(path)


class TestGroupedSplit:
    def test_split_by_farmer_never_puts_a_farmer_in_two_splits(self, tmp_path):
        data = [Item(f"x/{f}_{k}.jpg", IDS[k % 3]) for f in range(30) for k in range(6)]
        meta = metadata_file(
            tmp_path,
            [{"path": i.path, "farmer_code": f"F-{i.path[2:].split('_')[0]}"} for i in data],
            ["path", "farmer_code"],
        )
        assert grouped_split(data, meta) == "farmer"
        splits_of = defaultdict(set)
        for i in data:
            splits_of[i.group].add(i.split)
        assert all(len(s) == 1 for s in splits_of.values())
        assert {i.split for i in data} == {"train", "val", "test"}

    def test_field_is_the_group_when_there_is_no_farmer_code(self, tmp_path):
        data = [Item(f"x/{k}.jpg", IDS[0]) for k in range(4)]
        meta = metadata_file(
            tmp_path,
            [{"filename": f"{k}.jpg", "field_id": f"FLD-{k // 2}"} for k in range(4)],
            ["filename", "field_id"],
        )
        assert grouped_split(data, meta) == "field"
        assert data[0].split == data[1].split and data[2].split == data[3].split

    def test_split_column_is_used_as_given(self, tmp_path):
        data = [Item("x/a.jpg", IDS[0]), Item("x/b.jpg", IDS[0])]
        meta = metadata_file(
            tmp_path,
            [{"path": "x/a.jpg", "farmer_code": "F-1", "split": "test"},
             {"path": "x/b.jpg", "farmer_code": "F-2", "split": "train"}],
            ["path", "farmer_code", "split"],
        )  # fmt: skip
        assert grouped_split(data, meta) == "metadata"
        assert [i.split for i in data] == ["test", "train"]

    def test_a_farmer_in_two_splits_is_refused(self, tmp_path):
        data = [Item("x/a.jpg", IDS[0]), Item("x/b.jpg", IDS[0])]
        meta = metadata_file(
            tmp_path,
            [{"path": "x/a.jpg", "farmer_code": "F-1", "split": "test"},
             {"path": "x/b.jpg", "farmer_code": "F-1", "split": "train"}],
            ["path", "farmer_code", "split"],
        )  # fmt: skip
        with pytest.raises(DatasetError, match="F-1 is in more than one split"):
            grouped_split(data, meta)

    def test_images_missing_from_metadata(self, tmp_path):
        data = [Item("x/a.jpg", IDS[0])]
        meta = metadata_file(tmp_path, [{"path": "x/zzz.jpg", "farmer_code": "F-1"}], ["path", "farmer_code"])
        with pytest.raises(DatasetError, match="x/a.jpg: not in the metadata"):
            grouped_split(data, meta)

    def test_duplicate_filenames_are_refused(self, tmp_path):
        with pytest.raises(DatasetError, match="more than once"):
            metadata_file(
                tmp_path,
                [
                    {"filename": "IMG_1.jpg", "farmer_code": "F-1"},
                    {"filename": "IMG_1.jpg", "farmer_code": "F-2"},
                ],
                ["filename", "farmer_code"],
            )


def test_smoke_sample_spreads_over_classes():
    data = items({IDS[0]: 30, IDS[1]: 30, IDS[2]: 2})
    picked = smoke_sample(data, 20)
    assert len(picked) == 20
    assert Counter(i.class_id for i in picked) == {IDS[0]: 9, IDS[1]: 9, IDS[2]: 2}
    assert [i.path for i in smoke_sample(data, 20)] == [i.path for i in picked]


def test_class_weights_balance_classes_and_cover_every_index():
    data = items({IDS[0]: 30, IDS[1]: 10})
    for i in data:
        i.split = "train"
    weights = class_weights(data, IDS)
    assert len(weights) == 19
    assert weights[0] * 30 == pytest.approx(weights[1] * 10)  # each class contributes equally
    assert weights[0] == pytest.approx(40 / (2 * 30))
    assert weights[5] == 1.0  # no images: neutral


class TestMetrics:
    def test_confusion_matrix_and_scores(self):
        ids = ["a", "b", "c"]
        matrix = confusion_matrix([0, 0, 0, 1, 1, 2], [0, 0, 1, 1, 0, 2], 3)
        assert matrix == [[2, 1, 0], [1, 1, 0], [0, 0, 1]]
        a, b, c = per_class_metrics(matrix, ids)
        assert (a["precision"], a["recall"]) == (pytest.approx(2 / 3), pytest.approx(2 / 3))
        assert b["f1"] == pytest.approx(0.5) and c["f1"] == 1.0
        summary = summary_metrics(matrix, [a, b, c])
        assert summary["accuracy"] == pytest.approx(4 / 6) and summary["classes_evaluated"] == 3

    def test_classes_without_data_are_none_not_zero(self):
        matrix = confusion_matrix([0, 0], [0, 1], 3)
        a, b, c = per_class_metrics(matrix, ["a", "b", "c"])
        assert b["recall"] is None and b["precision"] == 0.0  # predicted but never true
        assert c == {"class_id": "c", "precision": None, "recall": None, "f1": None, "support": 0}
        assert summary_metrics(matrix, [a, b, c])["classes_evaluated"] == 1

    def test_csv_files(self, tmp_path):
        matrix = confusion_matrix([0, 1], [0, 0], 2)
        write_metrics_csv(tmp_path / "r.csv", per_class_metrics(matrix, ["a", "b"]))
        write_confusion_csv(tmp_path / "c.csv", matrix, ["a", "b"])
        assert (tmp_path / "r.csv").read_text().splitlines()[2] == "b,no data,0.0,no data,1"
        assert (tmp_path / "c.csv").read_text().splitlines() == ["true \\ predicted,a,b", "a,1,0", "b,1,0"]


def test_run_config_records_flags_counts_and_versions(tmp_path):
    mapping = write(tmp_path / "m.csv", "source,class_id\n")
    data = items({IDS[0]: 10})
    stratified_split(data)
    config = run_config(
        {"seed": 42, "model_version": "2026.10.0", "mapping": mapping, "smoke": False},
        split_method="stratified-random",
        counts=split_counts(data, IDS),
        empty=IDS[1:],
        skipped={"tomato": 4},
        versions={"tensorflow": "2.18.1"},
        git={"commit": "abc", "dirty": False},
    )
    assert config["seed"] == 42 and config["flags"]["mapping"] == str(mapping)
    assert len(config["mapping_sha256"]) == 64
    assert config["images_per_class"][IDS[0]] == {"train": 6, "val": 2, "test": 2}
    assert config["images_per_class"][IDS[1]] == {"train": 0, "val": 0, "test": 0}
    assert config["totals"] == {"train": 6, "val": 2, "test": 2}
    assert config["classes_without_images"][0] == IDS[1]


def test_training_and_export_scripts_import_without_tensorflow(monkeypatch):
    """CI has no TensorFlow: the scripts must only import it inside the functions that need it."""
    for name in ("tensorflow", "keras", "tensorflowjs"):
        monkeypatch.setitem(sys.modules, name, None)  # any import of these now raises ImportError
    for name in ("train_baseline", "export_tfjs"):
        monkeypatch.delitem(sys.modules, name, raising=False)
    import export_tfjs
    import train_baseline

    assert train_baseline.parse_args(["--smoke"]).epochs_head == 1
    assert export_tfjs.MAX_SHARD_BYTES == 4 * 1024 * 1024
