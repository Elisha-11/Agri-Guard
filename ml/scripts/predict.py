"""Run a trained model on photos and show what the app would tell the farmer for each one.

Usage:  python ml/scripts/predict.py ml/runs/<run> photo.jpg
        python ml/scripts/predict.py ml/runs/<run> <folder> --expect maize__lethal_necrosis --csv results.csv

<run> is a train_baseline.py run folder (saved_model/ and labels.json). Folders are searched recursively.
For each photo it prints the top 3 classes and the status the PWA would show (docs/model-output.md §4):
`confident`, `uncertain` or `consult`. With --expect (all photos are of one class) it also counts how many the
model got right, and how many wrong answers it would have shown as `confident`: the mistakes a farmer acts on.

Photos are loaded and resized exactly as the validation and test splits are in training. This is for trying a
model by hand; the scores in metrics.json come from the held-out test split and are the ones to report.
TensorFlow is imported only inside predict().
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from dataset import IMAGE_SUFFIXES, LABELS, DatasetError, class_ids, load_labels

# Initial thresholds from docs/model-output.md §4. Re-tuned in Step 6; the app reads them from manifest.json.
CONFIDENT = 0.70
UNCERTAIN = 0.40
TOP_K = 3


def status_for(confidence, confident=CONFIDENT, uncertain=UNCERTAIN):
    """The PWA's result status for a top-1 confidence."""
    if confidence >= confident:
        return "confident"
    if confidence >= uncertain:
        return "uncertain"
    return "consult"


def top_k(probs, ids, k=TOP_K):
    """The k most likely (class_id, probability) pairs, most likely first."""
    order = sorted(range(len(probs)), key=lambda i: probs[i], reverse=True)
    return [(ids[i], float(probs[i])) for i in order[:k]]


def find_images(paths):
    """Image files from files and folders (recursive), in a stable order. Unknown files are skipped."""
    found = []
    for path in map(Path, paths):
        if path.is_dir():
            found += sorted(p for p in path.rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES)
        elif path.is_file():
            found.append(path)
        else:
            raise DatasetError([f"{path}: no such file or folder"])
    return found


def summarise(results, expect=None):
    """Counts of top-1 class and status, plus right/wrong against --expect when given."""
    summary = {"photos": len(results), "top1": {}, "status": {}}
    for r in results:
        summary["top1"][r["top"][0][0]] = summary["top1"].get(r["top"][0][0], 0) + 1
        summary["status"][r["status"]] = summary["status"].get(r["status"], 0) + 1
    if expect:
        wrong = [r for r in results if r["top"][0][0] != expect]
        summary["correct"] = len(results) - len(wrong)
        summary["wrong_but_confident"] = sum(r["status"] == "confident" for r in wrong)
    return summary


def predict(run, images, ids):
    """Top-k classes and status for each image, using the run's saved_model."""
    import tensorflow as tf
    from train_baseline import IMAGE_SIZE, load_image

    infer = tf.saved_model.load(str(run / "saved_model")).signatures["serving_default"]
    results = []
    for path in images:
        image = tf.image.resize(load_image(str(path)), [IMAGE_SIZE, IMAGE_SIZE])
        probs = list(infer(image[tf.newaxis]).values())[0].numpy()[0]
        if len(probs) != len(ids):
            raise DatasetError([f"model has {len(probs)} outputs, labels.json has {len(ids)} classes"])
        top = top_k(probs, ids)
        results.append({"path": path, "top": top, "status": status_for(top[0][1])})
    return results


def write_csv(path, results):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["path", "status"] + [f"{h}{n}" for n in range(1, TOP_K + 1) for h in ("class", "p")])
        for r in results:
            writer.writerow([r["path"], r["status"]] + [v for c, p in r["top"] for v in (c, f"{p:.4f}")])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("run", type=Path, help="run folder with saved_model/ and labels.json")
    parser.add_argument("images", nargs="+", help="photos or folders of photos")
    parser.add_argument(
        "--expect", metavar="CLASS_ID", help="the class every photo shows, to count right/wrong"
    )
    parser.add_argument("--csv", type=Path, help="also write one row per photo to this CSV")
    args = parser.parse_args(argv)

    try:
        if not (args.run / "saved_model").is_dir():
            raise DatasetError([f"{args.run}: no saved_model/ folder (give the run folder, not saved_model)"])
        labels_path = args.run / "labels.json"
        ids = class_ids(load_labels(labels_path if labels_path.is_file() else LABELS))
        if args.expect and args.expect not in ids:
            raise DatasetError([f"--expect {args.expect}: not a class in labels.json"])
        images = find_images(args.images)
        if not images:
            raise DatasetError(["no .jpg, .jpeg or .png photos found"])
        results = predict(args.run, images, ids)
    except DatasetError as e:
        print("\n".join(e.problems), file=sys.stderr)
        return 1

    width = max(len(r["path"].name) for r in results)
    for r in results:
        top = "  ".join(f"{c} {p:.0%}" for c, p in r["top"])
        print(f"{r['path'].name:{width}}  {r['status']:9}  {top}")

    summary = summarise(results, args.expect)
    print(f"\n{summary['photos']} photos")
    print(
        "Top answer: "
        + ", ".join(f"{c} {n}" for c, n in sorted(summary["top1"].items(), key=lambda x: -x[1]))
    )
    print(
        "Status:     "
        + ", ".join(f"{s} {n}" for s, n in sorted(summary["status"].items(), key=lambda x: -x[1]))
    )
    if args.expect:
        print(f"Correct:    {summary['correct']} of {summary['photos']} ({args.expect})")
        print(f"Wrong but shown as confident: {summary['wrong_but_confident']}")
    if args.csv:
        write_csv(args.csv, results)
        print(f"Wrote {args.csv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
