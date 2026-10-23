"""Train a baseline EfficientNetB0 classifier for the classes in ml/labels.json (Build Step 5).

Usage (Colab, GPU):
    python ml/scripts/train_baseline.py --images /content/data/images --mapping ml/mappings/public.csv
Quick end-to-end check (CPU, a few minutes, no dataset needed):
    python ml/scripts/train_baseline.py --smoke

The output layer is labels.json's classes in index order, classes without images included. The model takes
raw RGB in [0, 255] at 224x224; EfficientNet's own preprocessing is inside the graph (docs/model-output.md).
Augmentation happens in the tf.data pipeline only, so the saved model is just backbone + head (ADR 0014).

Writes to the run folder: run_config.json, history.json, metrics.json, classification_report.csv,
confusion_matrix.csv/.png, labels.json and saved_model/. Export with export_tfjs.py. See docs/ml/training.md.
TensorFlow is imported inside the functions that need it, so CI can import this module without it.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import platform
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from dataset import (
    LABELS,
    ROOT,
    DatasetError,
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

IMAGE_SIZE = 224
DEFAULT_MODEL_VERSION = "2026.10.0"  # registrable (YYYY.MM.N); mark it a baseline in register_model --notes
TOP_BLOCKS = ("block6", "block7", "top_")  # unfrozen in stage 2
SMOKE_IMAGES = 20


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--images", type=Path, help="folder with one sub-folder per source class")
    parser.add_argument("--mapping", type=Path, help="CSV source,class_id mapping folders to labels.json ids")
    parser.add_argument("--metadata", type=Path, help="CSV with path/filename + farmer_code/field_id/split")
    parser.add_argument("--labels", type=Path, default=LABELS)
    parser.add_argument("--out", type=Path, help="run folder (default ml/runs/<version>-<time>)")
    parser.add_argument("--model-version", default=DEFAULT_MODEL_VERSION)
    parser.add_argument("--epochs-head", type=int, default=10, help="stage 1: frozen backbone")
    parser.add_argument("--epochs-finetune", type=int, default=20, help="stage 2: top blocks, early stopping")
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--lr-head", type=float, default=1e-3)
    parser.add_argument("--lr-finetune", type=float, default=1e-5)
    parser.add_argument("--patience", type=int, default=4, help="early stopping patience (epochs)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--weights", choices=["imagenet", "none"], default="imagenet")
    parser.add_argument(
        "--smoke", action="store_true", help="1 epoch per stage, ~20 images, CPU, then export + check_export"
    )
    args = parser.parse_args(argv)
    if not args.smoke and not (args.images and args.mapping):
        parser.error("--images and --mapping are required (or use --smoke)")
    if bool(args.images) != bool(args.mapping):
        parser.error("--images and --mapping go together")
    if args.smoke:
        args.epochs_head = args.epochs_finetune = 1
        args.batch_size = min(args.batch_size, 8)
    return args


def log(message=""):
    print(message, flush=True)


def git_state():
    def run(*cmd):
        return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=False).stdout.strip()

    return {
        "commit": run("git", "rev-parse", "HEAD") or None,
        "dirty": bool(run("git", "status", "--porcelain")),
    }


# --- TensorFlow parts ---------------------------------------------------------------------------------------


def make_synthetic_dataset(folder, ids, per_class=5):
    """A few random 256x256 JPEGs in folders named after class ids, plus an identity mapping, for --smoke."""
    import tensorflow as tf

    folder.mkdir(parents=True, exist_ok=True)
    chosen = ids[: max(1, math.ceil(SMOKE_IMAGES / per_class))]
    for k, class_id in enumerate(chosen):
        (folder / class_id).mkdir(exist_ok=True)
        for n in range(per_class):
            pixels = tf.random.stateless_uniform([256, 256, 3], seed=[k, n], maxval=256, dtype=tf.int32)
            tf.io.write_file(
                str(folder / class_id / f"{n}.jpg"), tf.io.encode_jpeg(tf.cast(pixels, tf.uint8))
            )
    mapping = folder.parent / "mapping.csv"
    mapping.write_text("source,class_id\n" + "".join(f"{c},{c}\n" for c in chosen), encoding="utf-8")
    return mapping


def load_image(path):
    import tensorflow as tf

    image = tf.io.decode_image(tf.io.read_file(path), channels=3, expand_animations=False)
    image.set_shape([None, None, 3])
    return tf.cast(image, tf.float32)  # 0-255, as the PWA feeds it


def rotate(image, angle):
    """Rotate about the centre (reflecting at the edges). Runs in tf.data only, never in the model."""
    import tensorflow as tf

    h, w = tf.cast(tf.shape(image)[0], tf.float32), tf.cast(tf.shape(image)[1], tf.float32)
    cos, sin = tf.cos(angle), tf.sin(angle)
    x_offset = ((w - 1) - (cos * (w - 1) - sin * (h - 1))) / 2
    y_offset = ((h - 1) - (sin * (w - 1) + cos * (h - 1))) / 2
    transform = tf.stack([cos, -sin, x_offset, sin, cos, y_offset, 0.0, 0.0])[None]
    return tf.raw_ops.ImageProjectiveTransformV3(
        images=image[None],
        transforms=transform,
        output_shape=tf.shape(image)[:2],
        fill_value=0.0,
        interpolation="BILINEAR",
        fill_mode="REFLECT",
    )[0]


def gaussian_blur(image, sigma):
    import tensorflow as tf

    x = tf.range(-2.0, 3.0)
    kernel_1d = tf.exp(-(x**2) / (2 * sigma**2))
    kernel_1d /= tf.reduce_sum(kernel_1d)
    kernel = tf.tile((kernel_1d[:, None] * kernel_1d[None, :])[:, :, None, None], [1, 1, 3, 1])
    return tf.nn.depthwise_conv2d(image[None], kernel, [1, 1, 1, 1], "SAME")[0]


def augment(image):
    """Farmer-photo variation: framing, orientation, tilt, light, focus."""
    import tensorflow as tf

    # Random crop of 70-100% of the area (farmers rarely frame the leaf the same way twice), then resize.
    begin, size, _ = tf.image.sample_distorted_bounding_box(
        tf.shape(image),
        bounding_boxes=tf.constant([[[0.0, 0.0, 1.0, 1.0]]]),
        min_object_covered=0.0,
        aspect_ratio_range=(0.8, 1.25),
        area_range=(0.7, 1.0),
        use_image_if_no_bounding_boxes=True,
    )
    image = tf.image.resize(tf.slice(image, begin, size), [IMAGE_SIZE, IMAGE_SIZE])
    image = tf.image.random_flip_left_right(image)
    image = tf.image.random_flip_up_down(image)
    image = tf.image.rot90(image, k=tf.random.uniform([], 0, 4, dtype=tf.int32))
    image = rotate(image, tf.random.uniform([], -0.26, 0.26))  # about +/- 15 degrees
    image = tf.image.random_brightness(image, max_delta=0.2 * 255)
    image = tf.image.random_contrast(image, 0.75, 1.25)
    image = tf.cond(
        tf.random.uniform([]) < 0.3,
        lambda: gaussian_blur(image, tf.random.uniform([], 0.5, 1.5)),
        lambda: image,
    )
    return tf.clip_by_value(image, 0.0, 255.0)


def make_dataset(images_dir, items, ids, batch_size, training, seed):
    import tensorflow as tf

    index = {c: k for k, c in enumerate(ids)}
    paths = [str(images_dir / i.path) for i in items]
    labels = [index[i.class_id] for i in items]
    ds = tf.data.Dataset.from_tensor_slices((paths, labels))
    if training:
        ds = ds.shuffle(len(paths), seed=seed, reshuffle_each_iteration=True)
    ds = ds.map(lambda p, y: (load_image(p), y), num_parallel_calls=tf.data.AUTOTUNE)
    if training:
        ds = ds.map(lambda x, y: (augment(x), y), num_parallel_calls=tf.data.AUTOTUNE)
    else:
        ds = ds.map(lambda x, y: (tf.image.resize(x, [IMAGE_SIZE, IMAGE_SIZE]), y))
    return ds.batch(batch_size).prefetch(tf.data.AUTOTUNE)


def build_model(n_classes, weights):
    """EfficientNetB0 (whose own Rescaling + Normalization take 0-255 input), pooling, dropout, softmax."""
    import keras

    inputs = keras.Input((IMAGE_SIZE, IMAGE_SIZE, 3), name="image", dtype="float32")
    backbone = keras.applications.EfficientNetB0(
        include_top=False,
        weights=None if weights == "none" else weights,
        input_shape=(IMAGE_SIZE, IMAGE_SIZE, 3),
    )
    backbone.trainable = False
    # training=False: BatchNormalization always runs in inference mode, in both stages.
    x = backbone(inputs, training=False)
    x = keras.layers.GlobalAveragePooling2D(name="pool")(x)
    x = keras.layers.Dropout(0.2, name="dropout")(x)
    outputs = keras.layers.Dense(n_classes, activation="softmax", name="probabilities", dtype="float32")(x)
    return keras.Model(inputs, outputs, name="agriguard_efficientnetb0"), backbone


def unfreeze_top_blocks(backbone):
    """Stage 2: train block6, block7 and the top conv. Every BatchNormalization layer stays frozen, so its
    moving statistics never change (small batches of farm photos would wreck the ImageNet statistics)."""
    import keras

    backbone.trainable = True
    for layer in backbone.layers:
        is_bn = isinstance(layer, keras.layers.BatchNormalization)
        layer.trainable = layer.name.startswith(TOP_BLOCKS) and not is_bn
    return sum(layer.trainable for layer in backbone.layers)


def fit(model, train_ds, val_ds, epochs, lr, weights, callbacks):
    import keras

    model.compile(
        optimizer=keras.optimizers.Adam(lr),
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"],
    )
    history = model.fit(
        train_ds, validation_data=val_ds, epochs=epochs, class_weight=weights, callbacks=callbacks, verbose=2
    )
    return {k: [float(v) for v in values] for k, values in history.history.items()}


def predict(model, ds):
    import numpy as np

    y_true, y_pred = [], []
    for x, y in ds:
        y_true += [int(v) for v in y.numpy()]
        y_pred += [int(v) for v in np.argmax(model.predict_on_batch(x), axis=1)]
    return y_true, y_pred


def plot_confusion(path, matrix, ids):
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        log("matplotlib not installed; skipping confusion_matrix.png")
        return
    fig, ax = plt.subplots(figsize=(12, 10))
    ax.imshow(matrix, cmap="Blues")
    ax.set_xticks(range(len(ids)), ids, rotation=90, fontsize=7)
    ax.set_yticks(range(len(ids)), ids, fontsize=7)
    ax.set_xlabel("predicted")
    ax.set_ylabel("true")
    for i, row in enumerate(matrix):
        for j, value in enumerate(row):
            if value:
                ax.text(j, i, value, ha="center", va="center", fontsize=6)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


# --- the run ------------------------------------------------------------------------------------------------


def prepare_data(args, ids, workdir):
    """Scan, sample (smoke) and split. Returns images_dir, items, split method and the scan."""
    images_dir, mapping_path = args.images, args.mapping
    if args.smoke and not images_dir:
        images_dir = workdir / "synthetic"
        mapping_path = make_synthetic_dataset(images_dir, ids)
        args.mapping = mapping_path
        log(f"--smoke: generated {SMOKE_IMAGES} synthetic images in {images_dir}")

    scan = scan_images(images_dir, parse_mapping(mapping_path, set(ids)), ids)
    for folder, n in scan.skipped.items():
        log(f"Skipped folder {folder!r} ({n} images): mapped to nothing")
    items = smoke_sample(scan.items, SMOKE_IMAGES, args.seed) if args.smoke else scan.items
    if not items:
        raise DatasetError(["no images found"])

    if args.metadata:
        method = grouped_split(items, read_metadata(args.metadata))
        log(f"Split by {method} (from {args.metadata.name}): no farmer or field is in two splits.")
    else:
        stratified_split(items, seed=args.seed)
        method = "stratified-random"
        log("WARNING: no field/farmer metadata, so this is a stratified RANDOM split. Use it for public data")
        log("WARNING: only. Test scores will overstate accuracy on new farms (docs/ml/splitting.md).")
    return images_dir, items, method, scan


def train(args):
    if args.smoke:
        os.environ["CUDA_VISIBLE_DEVICES"] = "-1"  # before TensorFlow is imported
    labels = load_labels(args.labels)
    ids = class_ids(labels)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out = args.out or ROOT / "ml" / "runs" / (
        f"smoke-{stamp}" if args.smoke else f"{args.model_version}-{stamp}"
    )
    out.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        images_dir, items, method, scan = prepare_data(args, ids, Path(tmp))
        counts = split_counts(items, ids)
        empty = [c for c in ids if not sum(counts[c].values())]
        log(f"\n{len(ids)} classes in labels.json; {len(ids) - len(empty)} have images.")
        if empty:
            log(f"No images for {len(empty)} classes (they keep their output unit, untrained):")
            log("\n".join(f"  {c}" for c in empty))
        totals = {s: sum(c[s] for c in counts.values()) for s in ("train", "val", "test")}
        log(f"Images: train {totals['train']}, val {totals['val']}, test {totals['test']}\n")
        if not totals["train"] or not totals["val"]:
            raise DatasetError(["need images in both train and val"])

        import keras
        import tensorflow as tf

        keras.utils.set_random_seed(args.seed)
        config = run_config(
            vars(args),
            split_method=method,
            counts=counts,
            empty=empty,
            skipped=scan.skipped,
            versions={
                "python": platform.python_version(),
                "tensorflow": tf.__version__,
                "keras": keras.__version__,
            },
            git=git_state(),
        )
        config["gpus"] = [d.name for d in tf.config.list_physical_devices("GPU")]
        (out / "run_config.json").write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

        train_items = [i for i in items if i.split == "train"]
        val_items = [i for i in items if i.split == "val"]
        test_items = [i for i in items if i.split == "test"] or val_items
        train_ds = make_dataset(images_dir, train_items, ids, args.batch_size, True, args.seed)
        val_ds = make_dataset(images_dir, val_items, ids, args.batch_size, False, args.seed)
        test_ds = make_dataset(images_dir, test_items, ids, args.batch_size, False, args.seed)
        weights = class_weights(items, ids)

        model, backbone = build_model(len(ids), args.weights)
        log(f"Stage 1: head only, {args.epochs_head} epochs, lr {args.lr_head}")
        history = {"head": fit(model, train_ds, val_ds, args.epochs_head, args.lr_head, weights, [])}

        n_trainable = unfreeze_top_blocks(backbone)
        log(f"Stage 2: fine-tune {n_trainable} backbone layers (BatchNorm frozen), lr {args.lr_finetune}")
        callbacks = [
            keras.callbacks.EarlyStopping(patience=args.patience, restore_best_weights=True),
            keras.callbacks.ReduceLROnPlateau(factor=0.3, patience=max(1, args.patience // 2)),
        ]
        history["finetune"] = fit(
            model, train_ds, val_ds, args.epochs_finetune, args.lr_finetune, weights, callbacks
        )
        (out / "history.json").write_text(json.dumps(history, indent=2) + "\n", encoding="utf-8")

        evaluated_on = "test" if any(i.split == "test" for i in items) else "val"
        y_true, y_pred = predict(model, test_ds)

    if model.output_shape[-1] != len(ids):
        raise DatasetError([f"model has {model.output_shape[-1]} outputs, labels.json has {len(ids)}"])
    matrix = confusion_matrix(y_true, y_pred, len(ids))
    per_class = per_class_metrics(matrix, ids)
    metrics = {"evaluated_on": evaluated_on, **summary_metrics(matrix, per_class), "per_class": per_class}
    (out / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    write_metrics_csv(out / "classification_report.csv", per_class)
    write_confusion_csv(out / "confusion_matrix.csv", matrix, ids)
    plot_confusion(out / "confusion_matrix.png", matrix, ids)

    run_labels = {**labels, "model_version": args.model_version}
    (out / "labels.json").write_text(json.dumps(run_labels, indent=2) + "\n", encoding="utf-8")
    model.export(
        str(out / "saved_model"), verbose=False
    )  # serving_default: image [None,224,224,3] -> [None,N]
    log(f"\n{evaluated_on} accuracy {metrics['accuracy']:.3f}, macro F1 {metrics['macro_f1'] or 0:.3f}")
    log(f"Wrote {out}")
    return out


def main(argv=None):
    args = parse_args(argv)
    try:
        out = train(args)
    except DatasetError as exc:
        log("Can't train:\n" + "\n".join(f"  {p}" for p in exc.problems))
        return 1
    if args.smoke:
        from export_tfjs import convert_and_check

        log("\n--smoke: exporting to TF.js and checking the folder")
        problems = convert_and_check(out / "saved_model", out / "export", out / "labels.json")
        if problems:
            log("Export check FAILED:\n" + "\n".join(f"  {p}" for p in problems))
            return 1
        log(f"Smoke run passed: {out / 'export' / args.model_version} is ready for register_model.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
