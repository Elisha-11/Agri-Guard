# AgriGuard ML

Owner: **Developer A (Elisha Lungu)**. Build Steps 3–7.

```
ml/
├── labels.json          GENERATED from docs/class-taxonomy.md; never edit by hand
├── scripts/
│   └── build_labels.py  regenerate labels.json after a taxonomy change
├── notebooks/           Colab notebooks (clear outputs before committing)
├── tests/
└── data/                DVC-tracked, git-ignored: raw/ interim/ processed/
```

## Class labels

```bash
python ml/scripts/build_labels.py                      # after editing docs/class-taxonomy.md
python ml/scripts/build_labels.py --model-version 2026.11.0
```

The index order in `labels.json` is the order of the model's output layer and is shared with the PWA
(see `docs/model-output.md`). Never reorder; retire classes instead.

## Data (Steps 3–4)

- Raw field photos go to Google Drive the same evening, unedited, with a metadata CSV per batch:
  `filename, crop, suspected_class, stage, gps_lat, gps_lng, captured_at, photographer, zone`.
- Datasets are tracked with DVC, not Git: `dvc init`, `dvc remote add -d gdrive gdrive://<folder-id>`.
- Split **by field and by farmer**, never by random shuffle, so the test set measures real generalisation.

## Targets (Step 6 exit condition)

- ≥ 85% held-out test accuracy across all five crops
- no class below 70% recall
- TF.js bundle < 15 MB, loads in < 5 s on a 1 GB RAM phone
