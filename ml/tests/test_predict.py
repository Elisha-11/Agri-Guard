"""predict.py's TensorFlow-free parts: statuses, top-k, finding photos, the summary and argument checks."""

import csv
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from dataset import DatasetError  # noqa: E402
from predict import find_images, main, status_for, summarise, top_k, write_csv  # noqa: E402

IDS = ["maize__healthy", "maize__grey_leaf_spot", "maize__common_rust", "maize__lethal_necrosis"]


def result(top1, p, status=None):
    return {"path": Path("x.jpg"), "top": [(top1, p)], "status": status or status_for(p)}


class TestStatus:
    @pytest.mark.parametrize(
        "confidence, status",
        [
            (0.95, "confident"),
            (0.70, "confident"),
            (0.69, "uncertain"),
            (0.40, "uncertain"),
            (0.39, "consult"),
        ],
    )
    def test_matches_model_output_thresholds(self, confidence, status):
        assert status_for(confidence) == status


class TestTopK:
    def test_most_likely_first(self):
        assert top_k([0.1, 0.6, 0.05, 0.25], IDS) == [
            ("maize__grey_leaf_spot", 0.6),
            ("maize__lethal_necrosis", 0.25),
            ("maize__healthy", 0.1),
        ]


class TestFindImages:
    def test_folders_are_searched_recursively_and_other_files_skipped(self, tmp_path):
        (tmp_path / "a" / "b").mkdir(parents=True)
        for name in ["a/1.jpg", "a/b/2.PNG", "a/notes.txt", "3.jpeg"]:
            (tmp_path / name).write_bytes(b"")
        found = find_images([tmp_path / "a", tmp_path / "3.jpeg"])
        assert [p.name for p in found] == ["1.jpg", "2.PNG", "3.jpeg"]

    def test_missing_path_is_an_error(self, tmp_path):
        with pytest.raises(DatasetError):
            find_images([tmp_path / "nope"])


class TestSummary:
    def test_counts_and_confident_mistakes(self):
        results = [
            result("maize__lethal_necrosis", 0.9),
            result("maize__healthy", 0.8),  # wrong, and the farmer would be told it confidently
            result("maize__healthy", 0.5),  # wrong, but shown as "not sure"
        ]
        summary = summarise(results, expect="maize__lethal_necrosis")
        assert summary["top1"] == {"maize__lethal_necrosis": 1, "maize__healthy": 2}
        assert summary["status"] == {"confident": 2, "uncertain": 1}
        assert (summary["correct"], summary["wrong_but_confident"]) == (1, 1)

    def test_no_right_or_wrong_without_expect(self):
        assert "correct" not in summarise([result("maize__healthy", 0.8)])


def test_csv_has_one_row_per_photo(tmp_path):
    rows = [{"path": Path("a.jpg"), "status": "consult", "top": [(c, 0.3) for c in IDS[:3]]}]
    write_csv(tmp_path / "out.csv", rows)
    lines = list(csv.reader((tmp_path / "out.csv").open(encoding="utf-8")))
    assert lines[0] == ["path", "status", "class1", "p1", "class2", "p2", "class3", "p3"]
    assert lines[1][:4] == ["a.jpg", "consult", "maize__healthy", "0.3000"]


class TestArguments:
    def test_run_without_saved_model_is_refused(self, tmp_path, capsys):
        assert main([str(tmp_path), str(tmp_path)]) == 1
        assert "no saved_model/" in capsys.readouterr().err

    def test_unknown_expected_class_is_refused(self, tmp_path, capsys):
        (tmp_path / "saved_model").mkdir()
        assert main([str(tmp_path), str(tmp_path), "--expect", "maize__nope"]) == 1
        assert "not a class" in capsys.readouterr().err

    def test_folder_without_photos_is_refused(self, tmp_path, capsys):
        (tmp_path / "saved_model").mkdir()
        (tmp_path / "photos").mkdir()
        assert main([str(tmp_path), str(tmp_path / "photos")]) == 1
        assert "no .jpg" in capsys.readouterr().err
