# AgriGuard documentation

Start here. Every document in the project is listed below; if you add one, add it here in the same pull request.

## Contract (backend ↔ PWA ↔ model)

Changes to these need approval from all three owners (see [CONTRIBUTING](../CONTRIBUTING.md#changing-the-contract)).

| Document | What it covers |
|----------|----------------|
| [api-contract.yaml](api-contract.yaml) | OpenAPI 3.1 spec, the source of truth for every endpoint. Rendered live at `http://localhost:8000/api/docs/`. |
| [model-output.md](model-output.md) | Files published with each model, `labels.json`, the prediction object, confidence thresholds, severity |
| [offline-sync.md](offline-sync.md) | Sync queue, idempotency on `client_id`, per-item results, clock skew, location privacy |
| [class-taxonomy.md](class-taxonomy.md) | **Draft** list of 19 crop/disease classes, with the open questions for the agronomist |

## Component guides

| Document | What it covers |
|----------|----------------|
| [../backend/README.md](../backend/README.md) | Running, checking and laying out the Django API; backend conventions |
| [backend/data-model.md](backend/data-model.md) | Every backend model, how it maps to the contract, and the rules the database enforces |
| [backend/auth.md](backend/auth.md) | Phone + SMS code sign-in: endpoints, limits, tokens, SMS setup, PWA guidance |
| [backend/profile-and-farms.md](backend/profile-and-farms.md) | `/me/` and `/farms/`: payloads, last-write-wins, idempotent farm creation |
| [backend/advisory-bundle.md](backend/advisory-bundle.md) | `GET /advisory/bundle/`: content rules, language fallback, ETag caching, writing advice, sample data |
| [backend/diagnosis-history.md](backend/diagnosis-history.md) | `GET /diagnoses/`: restoring history onto a new phone, cursor paging, `since` |
| [backend/diagnosis-photo.md](backend/diagnosis-photo.md) | `PUT /diagnoses/{client_id}/photo/`: photo consent, size and JPEG checks, metadata stripping, storage |
| [backend/feedback.md](backend/feedback.md) | `POST /feedback/`: who can give feedback, corrections, idempotency, queue order |
| [backend/model-releases.md](backend/model-releases.md) | `GET /model/latest/`; releasing a model step by step with `register_model`; rollback |
| [backend/diagnosis-sync.md](backend/diagnosis-sync.md) | `POST /diagnoses/sync/`: per-item results, validation, queue order, location consent, PWA checklist |
| [../ml/README.md](../ml/README.md) | Dataset layout, photo metadata, training and conversion |
| [ml/splitting.md](ml/splitting.md) | Train / val / test split by farmer with `split.py`: permanent assignments, class balance, warnings |
| [ml/field-data.md](ml/field-data.md) | Field photo routine, `metadata.csv` columns and values, `check_batch.py` errors and warnings |

## Decisions

Architecture Decision Records (ADRs) explain **why** something is the way it is. They live in
[decisions/](decisions/) and are never edited after they are accepted; a later ADR supersedes an earlier one instead.

| # | Decision | Status |
|---|----------|--------|
| [0001](decisions/0001-monorepo.md) | One repository with `ml/`, `backend/` and `pwa/` folders | Proposed |
| [0002](decisions/0002-confidence-thresholds.md) | Start with 0.70 / 0.40 confidence cut-offs, read from the manifest | Proposed (re-tune in Step 6) |
| [0003](decisions/0003-phone-based-user-model.md) | Farmer is the Django user model, keyed on phone number | Proposed |
| [0004](decisions/0004-coordinates-as-decimals.md) | Coordinates as two 3-dp decimals, not PostGIS (for now) | Proposed |
| [0005](decisions/0005-class-id-as-disease-key.md) | Class id string is the Disease primary key; diseases load only from labels.json | Proposed |
| [0006](decisions/0006-sms-otp-and-token-lifetimes.md) | SMS-code sign-in; 60-min access and 90-day rotating refresh tokens | Proposed |
| [0007](decisions/0007-diagnosis-sync-server-rules.md) | Sync: bad client_id is a 400, stored copy wins, farms first, location needs consent | Proposed |
| [0008](decisions/0008-advisory-bundle-content-rules.md) | Bundle: English fallback per disease with `lang`, content-hash version, app messages in the database | Proposed |
| [0009](decisions/0009-model-releases.md) | Model releases: `register_model` checks, one current release, rollback by switching | Proposed |
| [0010](decisions/0010-feedback-rules.md) | Feedback: owner or officer, self-reported role with sending account recorded, append-only | Proposed |
| [0011](decisions/0011-diagnosis-photo-rules.md) | Diagnosis photos: owner only, replace on resend, strip metadata on the server | Proposed |
| [0012](decisions/0012-field-photo-metadata.md) | Field photo metadata: field and farmer codes, fixed vocabularies, a checker before intake | Proposed |
| [0013](decisions/0013-farmer-level-split.md) | Split the dataset by farmer; a farmer's split never changes | Proposed |

To add one, copy [decisions/0000-template.md](decisions/0000-template.md) to the next number.

## History

[CHANGELOG.md](../CHANGELOG.md) records what changed in each release, newest first.

## How we document

See [CONTRIBUTING → Documentation](../CONTRIBUTING.md#documentation).
