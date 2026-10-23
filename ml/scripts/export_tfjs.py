"""Convert a trained SavedModel to the TF.js graph model the PWA loads; check it as register_model will.

Usage:  python ml/scripts/export_tfjs.py ml/runs/<run>/saved_model
        python ml/scripts/export_tfjs.py ml/runs/<run>/saved_model --out ml/exports --model-version 2026.10.0
        python ml/scripts/export_tfjs.py --check ml/exports/2026.10.0      # check an existing folder only

Weights are quantised to float16 (ADR 0014) and split into shards of at most 4 MB. labels.json (from the run
folder, or ml/labels.json) is copied alongside with model_version set. check_export() then repeats the file
and label checks of backend `manage.py register_model` (which needs Django, so can't be imported here), and
also checks the graph's input/output shapes and that every op runs in TF.js. Exits 1 on any problem.
TensorFlow and tensorflowjs are imported only inside convert().
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from dataset import LABELS, ROOT

MAX_SHARD_BYTES = 4 * 1024 * 1024  # backend register_model: shards of at most 4 MB
MAX_MODEL_BYTES = 15 * 1024 * 1024  # backend releases.MAX_MODEL_BYTES: model.json + shards
MODEL_VERSION = re.compile(r"^\d{4}\.\d{1,2}\.\d+$")  # backend validate_model_version (YYYY.MM.N)
ALLOWED_EXTRA = {"manifest.json"}  # written by register_model itself

# Ops the TF.js graph executor implements that an EfficientNet + dense head can produce after the converter's
# graph optimisation. Anything else is reported, so a new op is looked at before a phone fails to load it.
TFJS_OPS = {
    "Add", "AddN", "AddV2", "AvgPool", "BiasAdd", "Cast", "ConcatV2", "Const", "Conv2D",
    "DepthwiseConv2dNative", "Div", "DivNoNan", "Exp", "ExpandDims", "FusedBatchNorm", "FusedBatchNormV3",
    "FusedConv2D",
    "FusedDepthwiseConv2dNative", "Identity", "IdentityN", "MatMul", "Max", "Maximum", "MaxPool", "Mean",
    "Min", "Minimum", "Mul", "Neg", "NoOp", "Pack", "Pad", "PadV2", "Placeholder", "RealDiv", "Relu", "Relu6",
    "Reshape", "Rsqrt", "Shape", "Sigmoid", "Softmax", "Sqrt", "Square", "Squeeze", "StridedSlice", "Sub",
    "Sum", "Swish", "Tanh", "Transpose", "_FusedConv2D", "_FusedDepthwiseConv2dNative", "_FusedMatMul",
}  # fmt: skip
# Ops that only appear if training-time augmentation leaked into the exported graph (ADR 0014).
AUGMENTATION_OPS = {
    "AdjustContrastv2", "AdjustHue", "AdjustSaturation", "ImageProjectiveTransformV2",
    "ImageProjectiveTransformV3", "RandomShuffle", "RandomStandardNormal", "RandomUniform",
    "RandomUniformInt",
    "SampleDistortedBoundingBoxV2", "StatelessRandomUniformV2", "StatelessRandomGetKeyCounter",
    "StatelessRandomUniformIntV2", "StatelessRandomNormalV2", "RngReadAndSkip",
}  # fmt: skip


def graph_ops(model_json):
    """Every op used in model.json's graph, including inside functions."""
    topology = model_json.get("modelTopology", {})
    ops = {node.get("op") for node in topology.get("node", [])}
    for function in topology.get("library", {}).get("function", []):
        ops |= {node.get("op") for node in function.get("nodeDef", [])}
    return ops - {None}


def tensor_shape(spec):
    return [int(d.get("size", -1)) for d in spec.get("tensorShape", {}).get("dim", [])]


def check_signature(model_json, n_classes):
    signature = model_json.get("signature") or model_json.get("userDefinedMetadata", {}).get("signature")
    if not signature:
        return ["model.json has no signature, so input and output shapes can't be checked"]
    problems = []
    inputs, outputs = list(signature.get("inputs", {}).values()), list(signature.get("outputs", {}).values())
    if len(inputs) != 1 or len(outputs) != 1:
        return [f"expected 1 input and 1 output, got {len(inputs)} and {len(outputs)}"]
    shape, dtype = tensor_shape(inputs[0]), inputs[0].get("dtype")
    if shape[1:] != [224, 224, 3] or dtype != "DT_FLOAT":
        problems.append(f"input is {dtype} {shape}, expected DT_FLOAT [-1, 224, 224, 3]")
    if tensor_shape(outputs[0])[-1:] != [n_classes]:
        problems.append(f"output is {tensor_shape(outputs[0])}, expected [-1, {n_classes}] (labels.json)")
    return problems


def check_export(folder, reference_labels=LABELS):
    """Problems that would make register_model refuse the folder, or the PWA fail to run it. [] means fine."""
    folder = Path(folder)
    problems = []
    try:
        model_json = json.loads((folder / "model.json").read_text(encoding="utf-8"))
        labels = json.loads((folder / "labels.json").read_text(encoding="utf-8"))
        reference = json.loads(Path(reference_labels).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [f"can't read model.json / labels.json: {exc}"]

    manifest = model_json.get("weightsManifest")
    if not isinstance(manifest, list) or not manifest:
        return ["model.json has no weightsManifest; is this a TF.js graph model?"]
    shards = [name for group in manifest for name in group.get("paths", [])]
    total = (folder / "model.json").stat().st_size
    for name in shards:
        shard = folder / name
        if not shard.is_file():
            problems.append(f"model.json lists {name}, which isn't in the folder")
            continue
        size = shard.stat().st_size
        total += size
        if size > MAX_SHARD_BYTES:
            problems.append(f"{name} is {size:,} bytes; shards must be at most {MAX_SHARD_BYTES:,}")
    if total > MAX_MODEL_BYTES:
        problems.append(f"model.json + shards are {total / 2**20:.1f} MB; the limit is 15 MB")
    extra = sorted(
        p.name
        for p in folder.iterdir()
        if p.name not in {"model.json", "labels.json", *shards, *ALLOWED_EXTRA}
    )
    if extra:
        problems.append(f"unexpected files in the folder: {', '.join(extra)}")
    unquantised = [w["name"] for g in manifest for w in g.get("weights", []) if w.get("dtype") == "float32"
                   and w.get("quantization", {}).get("dtype") != "float16"]  # fmt: skip
    if unquantised:
        problems.append(
            f"{len(unquantised)} float32 weights are not float16-quantised, e.g. {unquantised[0]}"
        )

    version = labels.get("model_version", "")
    if folder.name != version:
        problems.append(f"folder is {folder.name!r} but labels.json model_version is {version!r}")
    if not MODEL_VERSION.match(version):
        problems.append(f"model_version {version!r} isn't YYYY.MM.N, so register_model will refuse it")
    for key in ("taxonomy_version", "input"):
        if labels.get(key) != reference.get(key):
            problems.append(f"labels.json {key} differs from {Path(reference_labels).name}")
    ours = [(c.get("index"), c.get("id")) for c in labels.get("classes", [])]
    theirs = [(c["index"], c["id"]) for c in reference["classes"]]
    if ours != theirs:
        problems.append("labels.json classes differ from ml/labels.json (order or ids)")

    problems += check_signature(model_json, len(theirs))
    ops = graph_ops(model_json)
    leaked = sorted(ops & AUGMENTATION_OPS)
    if leaked:
        problems.append(
            f"augmentation ops in the graph (augment in tf.data, not the model): {', '.join(leaked)}"
        )
    unknown = sorted(ops - TFJS_OPS - AUGMENTATION_OPS)
    if unknown:
        problems.append(f"ops not on the TF.js list in export_tfjs.py: {', '.join(unknown)}")
    return problems


def convert(saved_model_dir, folder):
    """SavedModel -> TF.js graph model in `folder` (float16 weights, shards of at most 4 MB)."""
    from tensorflowjs.converters import tf_saved_model_conversion_v2 as converter
    from tensorflowjs.quantization import QUANTIZATION_DTYPE_FLOAT16

    converter.convert_tf_saved_model(
        str(saved_model_dir),
        str(folder),
        signature_def="serving_default",
        saved_model_tags="serve",
        quantization_dtype_map={QUANTIZATION_DTYPE_FLOAT16: True},  # True: every weight
        weight_shard_size_bytes=MAX_SHARD_BYTES,
    )


def convert_and_check(saved_model_dir, out_dir, labels_path, model_version=None):
    """Convert into out_dir/<model_version>/, copy labels.json there, and return check_export()'s problems."""
    labels = json.loads(Path(labels_path).read_text(encoding="utf-8"))
    version = model_version or labels["model_version"]
    folder = Path(out_dir) / version
    if folder.exists() and any(folder.iterdir()):
        return [f"{folder} already exists and isn't empty; each version is exported once"]
    folder.mkdir(parents=True, exist_ok=True)
    convert(saved_model_dir, folder)
    (folder / "labels.json").write_text(
        json.dumps({**labels, "model_version": version}, indent=2) + "\n", encoding="utf-8"
    )
    problems = check_export(folder)
    print(f"Exported {folder}: {sum(p.stat().st_size for p in folder.iterdir()) / 2**20:.1f} MB")
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("saved_model", type=Path, nargs="?", help="the run's saved_model folder")
    parser.add_argument("--out", type=Path, default=ROOT / "ml" / "exports")
    parser.add_argument(
        "--labels", type=Path, help="default: labels.json next to saved_model, else ml/labels.json"
    )
    parser.add_argument("--model-version", help="default: from labels.json")
    parser.add_argument("--check", type=Path, metavar="FOLDER", help="only check an exported folder")
    args = parser.parse_args(argv)

    if args.check:
        problems = check_export(args.check)
    elif args.saved_model:
        labels = args.labels or next(
            (p for p in [args.saved_model.parent / "labels.json"] if p.is_file()), LABELS
        )
        problems = convert_and_check(args.saved_model, args.out, labels, args.model_version)
    else:
        parser.error("give a saved_model folder, or --check FOLDER")
    if problems:
        print("Export check FAILED:\n" + "\n".join(f"  {p}" for p in problems))
        return 1
    print("Export check passed: ready for `manage.py register_model`.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
