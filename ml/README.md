# AgriGuard ML

Owner: **Developer A (Elisha Lungu)**. Build Steps 3–7.

```
ml/
├── labels.json          GENERATED from docs/class-taxonomy.md; never edit by hand
├── scripts/
│   ├── build_labels.py  regenerate labels.json after a taxonomy change
│   ├── check_batch.py   check a field batch's photos and metadata.csv before intake
│   └── split.py         assign farmers to train / val / test and list every photo's split
├── splits/
│   └── farmers.csv      each farmer's split (written by split.py; never edit by hand)
├── templates/
│   └── metadata.csv     empty metadata.csv to start each batch from
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

- Raw field photos go to Google Drive the same evening, unedited, in a batch folder with a `metadata.csv`:
  `filename, crop, suspected_class, stage, field_id, farmer_code, gps_lat, gps_lng, captured_at, photographer,
  zone, notes`. Columns, allowed values and the routine: [docs/ml/field-data.md](../docs/ml/field-data.md).
- Check every batch before adding it: `python ml/scripts/check_batch.py <batch folder> --raw-dir ml/data/raw`.
- Datasets are tracked with DVC, not Git: `dvc init`, `dvc remote add -d gdrive gdrive://<folder-id>`.
- Split **by farmer**, never by random shuffle, so the test set measures real generalisation:
  `python ml/scripts/split.py`, then commit `ml/splits/farmers.csv`. See
  [docs/ml/splitting.md](../docs/ml/splitting.md).

## Targets (Step 6 exit condition)

- ≥ 85% held-out test accuracy across all five crops
- no class below 70% recall
- TF.js bundle < 15 MB, loads in < 5 s on a 1 GB RAM phone
