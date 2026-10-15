# AgriGuard documentation

Start here. Every document in the project is listed below; if you add one, add it here in the same pull request.

## Contract (backend ↔ PWA ↔ model)

Changes to these need approval from both developers (see [CONTRIBUTING](../CONTRIBUTING.md#changing-the-contract)).

| Document | What it covers |
|----------|----------------|
| [api-contract.yaml](api-contract.yaml) | OpenAPI 3.1 spec, the source of truth for every endpoint. Rendered live at `http://localhost:8000/api/docs/`. |
| [model-output.md](model-output.md) | Files published with each model, `labels.json`, the prediction object, confidence thresholds, severity |
| [offline-sync.md](offline-sync.md) | Sync queue, idempotency on `client_id`, per-item results, clock skew, location privacy |
| [class-taxonomy.md](class-taxonomy.md) | **Draft** list of 19 crop/disease classes, with the open questions for the agronomist |

## Component guides

| Document | What it covers |
|----------|----------------|
| [../backend/README.md](../backend/README.md) | Running, testing and structuring the Django API (added with the backend's first feature) |
| [../ml/README.md](../ml/README.md) | Dataset layout, photo metadata, training and conversion |

## Decisions

Architecture Decision Records (ADRs) explain **why** something is the way it is. They live in
[decisions/](decisions/) and are never edited after they are accepted; a later ADR supersedes an earlier one instead.

| # | Decision | Status |
|---|----------|--------|
| [0001](decisions/0001-monorepo.md) | One repository with `ml/`, `backend/` and `pwa/` folders | Proposed |
| [0002](decisions/0002-confidence-thresholds.md) | Start with 0.70 / 0.40 confidence cut-offs, read from the manifest | Proposed (re-tune in Step 6) |

To add one, copy [decisions/0000-template.md](decisions/0000-template.md) to the next number.

## History

[CHANGELOG.md](../CHANGELOG.md) records what changed in each release, newest first.

## How we document

See [CONTRIBUTING → Documentation](../CONTRIBUTING.md#documentation).
