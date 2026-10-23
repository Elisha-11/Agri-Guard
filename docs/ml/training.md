# Baseline training and TF.js export

How to train the baseline EfficientNetB0 model and export it for the PWA (Build Step 5). The goal of the baseline is
to prove the pipeline end to end (images → model → TF.js → `register_model` → phone), not accuracy. Design reasons
are in [ADR 0014](../decisions/0014-baseline-model-and-export.md); the split rules in [splitting.md](splitting.md).

Code: `ml/scripts/train_baseline.py`, `ml/scripts/export_tfjs.py`, and the TensorFlow-free logic they share in
`ml/scripts/dataset.py`.

## Input

**Images:** a folder with one sub-folder per *source* class, any depth inside, `.jpg`/`.jpeg`/`.png`:

```
images/
├── Corn_(maize)___Common_rust_/        IMG_001.jpg, ...
├── Corn_(maize)___healthy/
└── Tomato___Late_blight/               not ours: skipped through the mapping
```

**Mapping CSV** (`--mapping`): which of our class ids each source folder is. Every folder must be listed, so nothing
is silently dropped or mislabelled. Several folders can map to one class. An empty `class_id` (or `skip`) ignores the
folder.

```csv
source,class_id
Corn_(maize)___Common_rust_,maize__common_rust
Corn_(maize)___healthy,maize__healthy
Tomato___Late_blight,
```

Classes in labels.json with no images are allowed: the run lists them, they keep their output unit (so the output
size is always 19, in labels.json order), and the reports say `no data` for them.

**Metadata CSV** (`--metadata`, optional): how to split. With it, the split is **by farmer** (or by field), never by
photo:

| Column | |
|--------|---|
| `path` or `filename` | The image path relative to `--images` (preferred), or its file name if file names are unique |
| `farmer_code` / `field_id` | The group. Farmer wins when both are present |
| `split` | Optional. `train` / `val` / `test`, used as given (e.g. from `ml/data/processed/split.csv`, see splitting.md) |

Without `--metadata`, the run makes a stratified random 70 / 15 / 15 split and **prints a warning**: fine for a public
dataset, which has no farm information, but its test score will overstate accuracy on real farms.

## What a run does

1. Checks the mapping and folders, reports skipped folders and classes without images, then splits.
2. **Stage 1:** EfficientNetB0 (ImageNet weights) frozen; trains a new pooling + dropout + softmax head
   (`--epochs-head`, lr `--lr-head`).
3. **Stage 2:** unfreezes block6, block7 and the top convolution, **with every BatchNormalization layer kept frozen**,
   and fine-tunes at a low learning rate (`--epochs-finetune`, `--lr-finetune`) with early stopping on validation
   loss (`--patience`) and learning-rate reduction on plateaus. The best weights are kept.
4. Training images are augmented **in the tf.data pipeline** (never in the model): random crop of 70–100% of the
   area, flips, 90° turns, a ±15° tilt, brightness and contrast changes, and a slight blur on 30% of images.
   Validation and test images are only resized to 224 x 224.
5. Class weights balance the loss, so a class with few photos counts as much as a common one.
6. Evaluates on the test split (or val if test is empty) and writes the reports.

## Output (the run folder)

Default `ml/runs/<model_version>-<time>/` (git-ignored); on Colab, pass `--out` to a Drive folder.

| File | What it is |
|------|------------|
| `run_config.json` | Every flag, the seed, split method, mapping SHA-256, images per class per split, classes without images, skipped folders, Python/TF/Keras versions, GPUs, git commit (and whether it was dirty). Written before training starts |
| `history.json` | Loss and accuracy per epoch, for both stages |
| `metrics.json` | Accuracy, macro recall and F1 over classes with test images, and per-class numbers |
| `classification_report.csv` | Precision, recall, F1 and support per class (`no data` where undefined) |
| `confusion_matrix.csv` / `.png` | Rows are the true class, columns the predicted one, in labels.json order |
| `labels.json` | ml/labels.json with this run's `model_version` |
| `saved_model/` | The trained model (backbone + head only), input `image` `[None, 224, 224, 3]` float32 0–255, output `[None, 19]` |

## Export to TF.js

```bash
python ml/scripts/export_tfjs.py ml/runs/<run>/saved_model            # writes ml/exports/<model_version>/
python ml/scripts/export_tfjs.py --check ml/exports/2026.10.0         # re-check an existing folder
```

The export quantises weights to float16, writes shards of at most 4 MB, copies the run's labels.json, and then
checks the folder the way `manage.py register_model` will, plus a little more:

- exactly `model.json`, its shards and `labels.json` (and `manifest.json` once registered); no other files
- each shard ≤ 4,194,304 bytes; model.json + shards ≤ 15 MB; every weight float16
- labels.json identical to `ml/labels.json` apart from `model_version`; the folder named after `model_version`, which
  must be `YYYY.MM.N`
- the graph's input is float32 `[-1, 224, 224, 3]` and its output `[-1, 19]`
- every op in the graph is one TF.js runs, and **no augmentation op** leaked in

Any problem prints a list and exits 1.

## Registering the baseline

Baseline runs default to `--model-version 2026.10.0`, a real version so `register_model` accepts it unchanged. Say
it's a baseline in the notes and **don't make it current** on staging or production:

```bash
cd backend
python manage.py register_model ../ml/exports/2026.10.0 \
    --base-url https://elisha-11.github.io/agri-guard-models/models/2026.10.0/ --min-app-version 0.1.0 \
    --notes "Baseline: pipeline test only, not for farmers"
```

`2026.10.0` is already published (23 Oct 2026). Give any later run you mean to publish a new `--model-version`
(`2026.10.1`, `2026.11.0`, …): a published version never changes. Publishing steps are in
[model-releases.md](../backend/model-releases.md).

## Flags

| Flag | Default | |
|------|---------|---|
| `--images`, `--mapping` | | Required unless `--smoke` |
| `--metadata` | | Split by farmer/field (above) |
| `--out` | `ml/runs/<version>-<time>` | Run folder |
| `--model-version` | `2026.10.0` | Written into labels.json |
| `--epochs-head` / `--epochs-finetune` | 10 / 20 | Stage 2 usually stops early |
| `--batch-size` | 32 | Lower it if the GPU runs out of memory |
| `--lr-head` / `--lr-finetune` | 1e-3 / 1e-5 | |
| `--patience` | 4 | Early stopping, in epochs |
| `--seed` | 42 | Split, shuffling and initialisation |
| `--weights` | `imagenet` | `none` trains from scratch (only for offline tests) |
| `--smoke` | | See below |

## `--smoke`: test the whole pipeline in minutes

```bash
python ml/scripts/train_baseline.py --smoke                       # synthetic images, no dataset needed
python ml/scripts/train_baseline.py --smoke --images DIR --mapping CSV   # ~20 of your images
```

Runs on the CPU, 1 epoch per stage, about 20 images, then exports to `<run>/export/<model_version>/` and runs the
export check. It passes only if the folder would be accepted by `register_model`. Run it before every GPU session
and after changing anything in the pipeline. The scores mean nothing.

A smoke run on a laptop CPU (2026-10-21) took about 2 minutes, plus a one-off 16 MB download of the ImageNet
weights. It produced an 8.0 MB export in two shards, and `register_model` accepted it.

## Setup

Versions are pinned in `ml/requirements.txt` (TensorFlow 2.18.1, Keras 3.15.1, tensorflowjs 4.22.0). Use Python
3.11. The ml tests don't need any of this: they run with the backend venv.

### Google Colab (GPU runs)

Runtime → Change runtime type → GPU. Then, in cells:

```python
from google.colab import drive
drive.mount("/content/drive")
```

```bash
!git clone https://github.com/Elisha-11/Agri-Guard.git
%cd Agri-Guard
!pip install -q -r ml/requirements.txt
!python ml/scripts/train_baseline.py --smoke
!python ml/scripts/train_baseline.py \
    --images /content/drive/MyDrive/agri-guard/images \
    --mapping /content/drive/MyDrive/agri-guard/mapping.csv \
    --metadata /content/drive/MyDrive/agri-guard/metadata.csv \
    --out /content/drive/MyDrive/agri-guard/runs/2026.10.0
!python ml/scripts/export_tfjs.py /content/drive/MyDrive/agri-guard/runs/2026.10.0/saved_model \
    --out /content/drive/MyDrive/agri-guard/exports
```

Write runs and exports to Drive: the Colab disk is wiped when the session ends. If Colab restarts the
runtime after the pip install (it ships its own TensorFlow), rerun from `%cd Agri-Guard`. Run the smoke test first
in every session; it takes a few minutes and catches setup problems before the GPU hours start.

On Linux (Colab included) `pip install -r ml/requirements.txt` installs everything tensorflowjs asks for.

### Local, Windows (CPU: smoke runs and export only)

tensorflowjs depends on `tensorflow-decision-forests`, which has no Windows wheels. Install the converter without
its dependencies and add the few it uses for graph models:

```bash
py -3.11 -m venv C:\tf
C:\tf\Scripts\python -m pip install tensorflow==2.18.1 keras==3.15.1 numpy==2.0.2 pillow==13.0.0 matplotlib==3.11.2
C:\tf\Scripts\python -m pip install --no-deps tensorflowjs==4.22.0 tensorflow-hub==0.16.1 tf-keras==2.18.0
C:\tf\Scripts\python -m pip install importlib_resources jax==0.4.30 jaxlib==0.4.30
```

Two Windows problems, and their fixes:

- **"No such file or directory … calibration_statistics_pb2.py" during the TensorFlow install.** The path is
  longer than Windows allows. Put the venv on a short path (`C:\tf` above), or enable long paths (needs admin).
- **`ModuleNotFoundError: No module named 'tensorflow_decision_forests'` when converting.** The converter imports
  it at the top but only uses it for decision-forest models. Create an empty package in the venv:
  `C:\tf\Lib\site-packages\tensorflow_decision_forests\__init__.py`. Only do this on Windows, never on Colab.

Then, from the repo root: `C:\tf\Scripts\python ml/scripts/train_baseline.py --smoke`.
