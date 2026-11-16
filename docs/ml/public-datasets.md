# Public maize datasets

How open datasets are downloaded, cleaned, mapped to our classes and split, alongside the field photos in
[field-data.md](field-data.md). Attribution for every source is in [ml/CREDITS.md](../../ml/CREDITS.md).

## The two scripts

```bash
python ml/scripts/fetch_public.py --list               # sources, licences, status, sizes
python ml/scripts/fetch_public.py karaagro --extract   # download (resumable, MD5-checked) and unpack
python ml/scripts/public_maize.py                      # clean, map, group, split, report
python ml/scripts/public_maize.py --test-source zmld   # hold one source out as the whole test set
```

Pillow is needed for `public_maize.py` (it is in `ml/requirements.txt`). Everything is written under
`ml/data/` and stays out of git: `external/` (downloads, `sources.json`) and `interim/public_maize/`.

## Rules

- **Only approved sources download.** Each source in `fetch_public.py` has a status: `approved`,
  `not-approved` (licence fine, size not agreed) or `licence-unclear` (never download). Changing a status is a
  team decision, recorded in the PR.
- **Labels go through `ml/mappings/<source>.csv`** (`source,class_id,confirm,note`; the same `source,class_id`
  format `train_baseline.py --mapping` reads). An empty `class_id` keeps the images aside in `unmapped/`;
  `confirm=agronomist` marks a mapping the agronomist must confirm, listed in the report. Pests such as
  fall armyworm stay unmapped until class-taxonomy.md question 4 is answered.
- **Dropped:** augmented copies, unreadable files, images under 224 px on the short side (warning under
  600 px, as in `check_batch.py`), exact duplicates (SHA-256) and near-duplicates (dHash ≤ 4), including
  across sources. The copy from the higher-priority source is kept.
- **Grouping:** look-alikes (dHash ≤ 12, any source) share a `field_id` such as `PUB-000123`, and `split.py`'s
  `assign()` places whole groups, so near-identical photos never straddle train and test. Public groups are
  never written to `ml/splits/farmers.csv`, which is for real farmers.
- **Lab-style images** (PlantVillage and similar plain-background sets) are forced into train. They say
  nothing about field performance and must never be in val or test.

## Outputs (`ml/data/interim/public_maize/`)

| File | What |
|------|------|
| `<class_id>/<source>__<sha12>.jpg` | Kept images, byte-for-byte copies |
| `unmapped/<source>/<label>/` | Images whose label has no class yet |
| `metadata.csv` | `ml/templates/metadata.csv` columns plus `source, licence, original_label` (`stage=unknown`, no GPS, no zone) |
| `split.csv` | `filename, field_id, split` |
| `training_mapping.csv` | For `train_baseline.py --mapping` |
| `report.md` | Counts per class and source and split, drops by reason, classes under 300, mappings to confirm |

Train on it with:

```bash
python ml/scripts/train_baseline.py --images ml/data/interim/public_maize \
    --mapping ml/data/interim/public_maize/training_mapping.csv \
    --metadata ml/data/interim/public_maize/split.csv
```

## Sources (checked 2026-11-16)

| Source | Licence | Maize classes | Status |
|--------|---------|---------------|--------|
| KaraAgro AI Maize (Ghana), Harvard Dataverse | CC0 | healthy, fall armyworm, streak | approved: `healthy_01` + `maize_streak_01` only (4.3 of 41.2 GB) |
| Zambia Maize Leaf Dataset, Zenodo | CC BY 4.0 | GLS, NLB, MSV, healthy | downloaded, **excluded**: incomplete upload with contradictory labels |
| Maize Imagery Dataset – Tanzania, Mendeley | CC BY 4.0 | healthy, MLN, MSV | approved 2026-11-16: three zips, 7.49 GB, SHA-256 checked; the only MLN source |
| Crop Pest and Disease Detection (Ghana), Mendeley | CC BY 4.0 | healthy, leaf blight, leaf spot, streak, 3 pests | not approved yet. Only one 8.44 GB zip, but the 5,358 raw maize images (269 MB) can be range-read from it; never the augmented set |
| Wiesner-Hanks et al. 2018 NLB, OSF | none recorded | NLB | licence unclear: do not download |

No open field source with **common rust** was found. The class stays empty (the model keeps its output, and
reports say "no data") until field photos are collected.
