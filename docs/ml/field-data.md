# Field photos: metadata and batch checks

How field photos go from a phone to the dataset (Build Step 3), and what the metadata CSV must contain. Design
reasons are in [ADR 0012](../decisions/0012-field-photo-metadata.md).

## The routine

1. **Before the trip:** make sure every field you'll visit has a `field_id` and every farmer a `farmer_code` in the
   team's offline code sheet. Set iPhones to **Settings > Camera > Formats > Most Compatible** (JPEG, not HEIC).
   Turn on location for the camera if possible.
2. **In the field:** take photos at full resolution. One leaf per photo, filling most of the frame.
3. **The same evening:**
   1. Copy the photos, unedited, into a batch folder named `YYYY-MM-DD_<place>_<initials>`, e.g.
      `ml/data/raw/2026-10-20_chongwe_el/`.
   2. Fill in `metadata.csv` in that folder, starting from [`ml/templates/metadata.csv`](../../ml/templates/metadata.csv).
      One row per photo.
   3. Check it, and fix anything marked `ERROR`:

      ```bash
      python ml/scripts/check_batch.py ml/data/raw/2026-10-20_chongwe_el --raw-dir ml/data/raw
      ```

   4. When it reports 0 errors, upload the folder to Google Drive and run `dvc add` on it.

## Columns

| Column | Required | Values | Example |
|--------|----------|--------|---------|
| `filename` | yes | The photo's file name in the batch folder, `.jpg` or `.jpeg` | `IMG_0412.jpg` |
| `crop` | yes | `maize`, `groundnut`, `cassava`, `soybean`, `cotton` | `maize` |
| `suspected_class` | no | A class id from `ml/labels.json` for that crop. Leave empty or `unknown` if unsure | `maize__grey_leaf_spot` |
| `stage` | yes | `none` (healthy leaves only), `early`, `mid`, `advanced`, `unknown` | `mid` |
| `field_id` | yes | Team code for the field: capitals, digits and `-` | `CHG-014` |
| `farmer_code` | yes | Team code for the farmer. **Never a name or phone number** | `F-0007` |
| `gps_lat`, `gps_lng` | no | Decimal degrees, both or neither | `-15.416`, `28.283` |
| `captured_at` | yes | `2026-10-20 14:03` or `20/10/2026 14:03`. Lusaka time unless a zone is given | `2026-10-20 14:03` |
| `photographer` | yes | Initials | `EL` |
| `zone` | yes | Agro-ecological region: `I`, `IIa`, `IIb`, `III` | `IIa` |
| `notes` | no | Anything useful: weather, a second disease on the leaf, the officer present | `two lesion types` |

Save from Excel or Google Sheets as **CSV UTF-8**.

## What the checker reports

**Errors** (the batch can't go in until they're fixed):

- a missing column, a required value left empty, or a value not in the lists above
- a `suspected_class` from another crop; a healthy class with a stage other than `none`, or `none` on a disease
- a field listed under two different farmers
- GPS outside Zambia (usually latitude and longitude swapped)
- `captured_at` before 2026 or in the future (the phone's clock is wrong: fix the time, and note it)
- a photo listed in the CSV but missing, or in the folder but not in the CSV, or listed twice
- a photo that isn't a readable JPEG, is a HEIC, or is under 224 px on its short side
- the same photo twice in the batch, or already in an earlier batch (with `--raw-dir`)

**Warnings** (fine to add, but worth knowing): no `suspected_class` (it will need an expert label), no GPS, a photo
under 600 px on its short side, or columns the checker doesn't know.

The checker exits with code 1 when there are errors, so it can be used in scripts. It ends with a count per class,
to track progress toward 300 photos per class.

## Privacy

`farmer_code` and `field_id` keep names and phone numbers out of the dataset. Raw photos keep their EXIF
(including GPS) for the internal dataset only. Strip it before any image is published.
