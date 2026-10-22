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
| [backend/diagnosis-sync.md](backend/diagnosis-sync.md) | `POST /diagnoses/sync/`: per-item results, validation, queue order, location consent, PWA checklist |
| [../ml/README.md](../ml/README.md) | Dataset layout, photo metadata, training and conversion |

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

To add one, copy [decisions/0000-template.md](decisions/0000-template.md) to the next number.

## History

[CHANGELOG.md](../CHANGELOG.md) records what changed in each release, newest first.

## How we document

See [CONTRIBUTING → Documentation](../CONTRIBUTING.md#documentation).
