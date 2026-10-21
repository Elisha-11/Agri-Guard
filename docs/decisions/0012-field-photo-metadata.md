# 0012. Field photo metadata: field and farmer codes, fixed vocabularies, a checker before intake

- **Status:** Proposed (confirm at the Wednesday technical sync, then mark Accepted)
- **Date:** 2026-10-21
- **Deciders:** Elisha Lungu, Robert Ng'onga Chishangila

## Context

M2 (6,000+ field photos) is due on 2026-10-28. `ml/README.md` listed the metadata CSV columns as
`filename, crop, suspected_class, stage, gps_lat, gps_lng, captured_at, photographer, zone`, and also said the
train/val/test split must be **by field and by farmer**. No column says which field or farmer a photo came from,
so that split was impossible. `stage` and `zone` had no allowed values. Mistakes found weeks later, after Label
Studio import, cost far more than mistakes found the same evening.

## Decisions

1. **Add `field_id` and `farmer_code`** (and an optional `notes`). Both are short team-assigned codes such as
   `CHG-014` and `F-0007`, never names or phone numbers. The list linking codes to real farmers stays offline
   with the team lead. A field always belongs to one farmer.
2. **Fixed vocabularies:**
   - `stage`: `none` (healthy only), `early`, `mid`, `advanced` or `unknown`. These are the stages the agronomist
     is asked to define in class-taxonomy.md.
   - `zone`: Zambia's agro-ecological regions `I`, `IIa`, `IIb` or `III`.
   - `suspected_class`: a class id from `ml/labels.json`, or empty / `unknown` if the photographer isn't sure.
   - `photographer`: initials.
3. **Times without a time zone mean Lusaka time (UTC+2).** Spreadsheet dates (`dd/mm/yyyy hh:mm`) are accepted,
   because that's what the team's phones and Excel produce.
4. **`ml/scripts/check_batch.py` runs on every batch before `dvc add`.** Errors block intake; warnings don't. It
   uses only the standard library, so it runs on any laptop without the training environment.
5. **Photos must be JPEG**, at least 224 px on the short side (warning under 600 px). iPhone HEIC files are
   rejected with instructions. Exact duplicates are rejected within a batch and, with `--raw-dir`, against
   earlier batches.

## Alternatives considered

- **Split by GPS clusters instead of field codes:** GPS is optional (some phones have it off) and neighbouring
  farmers' fields sit close together.
- **Store farmer names in the CSV:** the dataset is shared on Google Drive and may be published later. Codes keep
  personal data out of it.
- **Validate in the training notebook:** too late. Problems need to be found while the photographer still
  remembers the field.

## Consequences

- Field teams need a code list before the first trip: one `field_id` per field and one `farmer_code` per
  farmer, kept in an offline sheet.
- Raw photos keep their EXIF (including GPS). That's fine for the internal dataset, but it must be stripped before
  any public release of images.
- The split script (next step) can group by `farmer_code`, so no farmer's photos appear in both train and test.
