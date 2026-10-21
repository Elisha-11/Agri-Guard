"""check_export(): the exported folder is exactly what register_model and the PWA expect. No TensorFlow."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from dataset import LABELS  # noqa: E402
from export_tfjs import MAX_SHARD_BYTES, check_export, main  # noqa: E402

REFERENCE = json.loads(LABELS.read_text(encoding="utf-8"))
VERSION = "2026.10.0"
# The ops in a real EfficientNetB0 export (train_baseline.py --smoke, TF 2.18.1, tensorflowjs 4.22.0).
EFFICIENTNET_OPS = [
    "Add", "AddN", "AddV2", "Const", "Conv2D", "DepthwiseConv2dNative", "Identity", "Mean", "Mul", "Pack",
    "Pad", "Placeholder", "Reshape", "Shape", "Sigmoid", "Softmax", "StridedSlice", "_FusedConv2D",
    "_FusedMatMul",
]  # fmt: skip


def signature(n_out=19, in_shape=(-1, 224, 224, 3), dtype="DT_FLOAT"):
    dims = lambda shape: {"dim": [{"size": str(s)} for s in shape]}  # noqa: E731
    return {
        "inputs": {"image:0": {"name": "image:0", "dtype": dtype, "tensorShape": dims(in_shape)}},
        "outputs": {
            "Identity:0": {"name": "Identity:0", "dtype": "DT_FLOAT", "tensorShape": dims((-1, n_out))}
        },
    }


def export(tmp_path, *, shards=(3_000_000, 3_000_000, 2_000_000), ops=EFFICIENTNET_OPS, sig=None, labels=None,
           version=VERSION, folder_name=None, quantised=True):  # fmt: skip
    """A fake TF.js export folder shaped like the converter's output."""
    folder = tmp_path / (folder_name or version)
    folder.mkdir()
    names = [f"group1-shard{k + 1}of{len(shards)}.bin" for k in range(len(shards))]
    for name, size in zip(names, shards, strict=True):
        (folder / name).write_bytes(bytes(size))
    quantization = {"dtype": "float16", "original_dtype": "float32"} if quantised else None
    weights = [{"name": "dense/kernel", "shape": [1280, 19], "dtype": "float32",
                **({"quantization": quantization} if quantization else {})}]  # fmt: skip
    model = {
        "format": "graph-model",
        "generatedBy": "2.18.1",
        "convertedBy": "TensorFlow.js Converter v4.22.0",
        "signature": signature() if sig is None else sig,
        "modelTopology": {
            "node": [{"name": f"n{k}", "op": op} for k, op in enumerate(ops)],
            "library": {},
            "versions": {"producer": 1882},
        },
        "weightsManifest": [{"paths": names, "weights": weights}],
    }
    (folder / "model.json").write_text(json.dumps(model), encoding="utf-8")
    labels = labels if labels is not None else {**REFERENCE, "model_version": version}
    (folder / "labels.json").write_text(json.dumps(labels), encoding="utf-8")
    return folder


def test_a_good_export_passes(tmp_path):
    assert check_export(export(tmp_path)) == []


def test_manifest_json_from_register_model_is_allowed(tmp_path):
    folder = export(tmp_path)
    (folder / "manifest.json").write_text("{}")
    assert check_export(folder) == []


@pytest.mark.parametrize(
    "kwargs, message",
    [
        ({"shards": (MAX_SHARD_BYTES + 1,)}, "shards must be at most 4,194,304"),
        ({"shards": (4_000_000,) * 4}, "the limit is 15 MB"),
        ({"version": "0.1.0-baseline"}, "isn't YYYY.MM.N"),
        ({"folder_name": "2026.11.0"}, "folder is '2026.11.0' but labels.json model_version is '2026.10.0'"),
        ({"sig": signature(n_out=18)}, "expected [-1, 19]"),
        ({"sig": signature(in_shape=(-1, 256, 256, 3))}, "expected DT_FLOAT [-1, 224, 224, 3]"),
        ({"sig": signature(dtype="DT_INT32")}, "expected DT_FLOAT"),
        ({"sig": {}}, "no signature"),
        ({"ops": [*EFFICIENTNET_OPS, "ImageProjectiveTransformV3"]}, "augmentation ops in the graph"),
        ({"ops": [*EFFICIENTNET_OPS, "StatelessRandomUniformV2"]}, "augmentation ops in the graph"),
        ({"ops": [*EFFICIENTNET_OPS, "Einsum"]}, "not on the TF.js list in export_tfjs.py: Einsum"),
        ({"quantised": False}, "not float16-quantised"),
    ],
)
def test_problems_are_reported(tmp_path, kwargs, message):
    problems = check_export(export(tmp_path, **kwargs))
    assert any(message in p for p in problems), problems


def test_a_15_mb_total_is_exactly_allowed(tmp_path):
    folder = export(tmp_path, shards=(MAX_SHARD_BYTES,) * 4)
    last = folder / "group1-shard4of4.bin"
    room = 15 * 2**20 - 3 * MAX_SHARD_BYTES - (folder / "model.json").stat().st_size
    last.write_bytes(bytes(room))
    assert check_export(folder) == []
    last.write_bytes(bytes(room + 1))
    assert any("limit is 15 MB" in p for p in check_export(folder))


def test_missing_shard_and_extra_file(tmp_path):
    folder = export(tmp_path)
    (folder / "group1-shard2of3.bin").unlink()
    (folder / "notes.txt").write_text("x")
    problems = check_export(folder)
    assert any("lists group1-shard2of3.bin, which isn't in the folder" in p for p in problems)
    assert any("unexpected files in the folder: notes.txt" in p for p in problems)


def test_labels_must_match_ml_labels_json(tmp_path):
    classes = [dict(c) for c in REFERENCE["classes"]]
    classes[0]["id"], classes[1]["id"] = classes[1]["id"], classes[0]["id"]
    problems = check_export(
        export(tmp_path, labels={**REFERENCE, "model_version": VERSION, "classes": classes})
    )
    assert "labels.json classes differ from ml/labels.json (order or ids)" in problems


def test_labels_taxonomy_and_input_must_match(tmp_path):
    labels = {**REFERENCE, "model_version": VERSION, "taxonomy_version": "0.2", "input": {"width": 256}}
    problems = check_export(export(tmp_path, labels=labels))
    assert "labels.json taxonomy_version differs from labels.json" in problems
    assert "labels.json input differs from labels.json" in problems


def test_ops_inside_functions_are_checked(tmp_path):
    folder = export(tmp_path)
    model = json.loads((folder / "model.json").read_text())
    model["modelTopology"]["library"] = {"function": [{"nodeDef": [{"op": "RandomUniform"}]}]}
    (folder / "model.json").write_text(json.dumps(model))
    assert any("RandomUniform" in p for p in check_export(folder))


def test_cli_check_exit_codes(tmp_path, capsys):
    assert main(["--check", str(export(tmp_path))]) == 0
    assert "ready for `manage.py register_model`" in capsys.readouterr().out
    (tmp_path / "other").mkdir()
    bad = export(tmp_path / "other", shards=(MAX_SHARD_BYTES + 1,))
    assert main(["--check", str(bad)]) == 1
