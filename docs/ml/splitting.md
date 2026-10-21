# Splitting the dataset: train, val and test by farmer

How field photos are divided into training, validation and test sets (Build Step 4). Design reasons are in
[ADR 0013](../decisions/0013-farmer-level-split.md). Field photos and their metadata are described in
[field-data.md](field-data.md).

## The rule

**All photos from one farmer go to one split, and a farmer never changes split.** Otherwise the model is tested
on farms it has already seen, and the test accuracy overstates how it will do for a new farmer.

## Running it

After adding new batches to `ml/data/raw/` (each one already passing `check_batch.py`):

```bash
python ml/scripts/split.py
git add ml/splits/farmers.csv && git commit -m "data: split farmers from batches up to 2026-10-20"
dvc add ml/data/processed/split.csv
```

Run it on **one machine** (the ML lead's), and commit `farmers.csv` straight away.

Options: `--ratios 0.7 0.15 0.15` (the default), `--raw-dir`, `--assignments`, `--out`.

## What it does

1. Checks every batch with `check_batch.py`, and that no field appears under two farmers across batches. If
   anything fails, it stops and writes nothing.
2. Reads `ml/splits/farmers.csv`. Farmers already in it keep their split.
3. Places each new farmer, largest first, in the split that keeps every class closest to 70 / 15 / 15.
4. Writes:
   - `ml/splits/farmers.csv` (git): `farmer_code, split`. This is the record that matters; never edit a
     farmer's split by hand.
   - `ml/data/processed/split.csv` (DVC): one row per photo with `batch, filename, split, farmer_code, field_id,
     crop, suspected_class`. Training reads this.
5. Prints photos per class per split, for example:

   ```
   class                                     train    val   test
   maize__common_rust                          557    105    117
   maize__lethal_necrosis                       80     40      0
   ...
   WARN  maize__lethal_necrosis: under 30 photos in val or test (more farmers needed)
   ```

## Reading the warnings

A class under 30 photos in val or test can't be measured reliably. The fix is **photos from more farmers** for
that class, not more photos from the same farmers and not moving farmers by hand. Rare diseases seen at only one
or two farms will keep showing this warning. Raise it with the agronomist (class-taxonomy.md asks the same
question about MLN).

Photos with no `suspected_class` are split like any other (their farmer decides the split) and counted as
`unknown` until they're labelled. Changing a label later never moves a photo between splits.
