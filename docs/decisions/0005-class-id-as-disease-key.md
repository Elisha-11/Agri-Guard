# 0005. Use the class id string as the Disease primary key, loaded only from labels.json

- **Status:** Proposed (confirm at the Wednesday technical sync, then mark Accepted)
- **Date:** 2026-10-15
- **Deciders:** Elisha Lungu, Robert Ng'onga Chishangila

## Context

The model, the PWA and the backend must agree on what each output class means. The PWA sends predictions as
`class_id` strings (e.g. `maize__grey_leaf_spot`) plus the integer `class_index`. The taxonomy rules say indices are
fixed forever and retired classes stay listed. If someone types the disease list into the admin by hand, it will
drift from `ml/labels.json`.

## Decision

- `catalog.Disease` uses `class_id` as its primary key, with `class_index` unique.
- Disease rows are created **only** by `manage.py load_taxonomy` from `ml/labels.json`. The admin can't add them.
- The loader refuses any change that would move an index, reuse one, or drop a class.

## Alternatives considered

- **Integer primary key plus a unique `class_id`:** conventional, but every incoming prediction then needs a lookup,
  and foreign keys in the database become unreadable numbers.
- **`class_index` as the primary key:** the index means nothing to a person reading the data, and it's tied to one
  model's output layout.

## Consequences

- Renaming a class id after a model has shipped would mean a data migration. The taxonomy is still a draft, so
  rename freely **until** the agronomist signs off and the first model is trained.
- Diagnoses and feedback stay readable in raw SQL and in exports.
