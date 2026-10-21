# Changelog

All notable changes to AgriGuard are recorded here, newest first. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and versions follow [Semantic Versioning](https://semver.org/).

Every pull request adds a line under **Unreleased** in the right group (Added, Changed, Fixed, Removed, Security).
On release, Unreleased is renamed to the version and date, and `main` is tagged.

## [Unreleased]

### Added

- Documentation system: `docs/README.md` index, Architecture Decision Records in `docs/decisions/` (ADR 0001
  monorepo, ADR 0002 confidence thresholds), this changelog, and a Documentation section in CONTRIBUTING.
- Backend data models in four new apps: `accounts.Farmer` (the user model, phone login, consent
  flags), `farms.Farm`, `catalog.Disease` and `catalog.DiseaseAdvice` (advice per language, publishable only after
  agronomist review), `diagnoses.Diagnosis` and `diagnoses.Feedback` (append-only, idempotent on `client_id`).
  Database constraints and validation follow the contract; see `docs/backend/data-model.md`.
- `manage.py load_taxonomy` loads the disease classes from `ml/labels.json` and refuses changes that would reorder
  them.
- Django admin for all models, including a phone-based "add farmer" form.
- Test that the backend's enums and phone pattern match `docs/api-contract.yaml`.
- `backend/README.md`, `docs/backend/data-model.md`, and ADRs 0003 (phone-based user model), 0004 (coordinates as
  decimals) and 0005 (class id as disease key).
- Phone sign-in (contract `/auth/otp/request/`, `/auth/otp/verify/`, `/auth/token/refresh/`): 6-digit SMS codes,
  hashed at rest, 10-minute lifetime, 3 requests per phone per 15 minutes, 5 guesses per code; the farmer account
  is created on first sign-in. 60-minute access tokens, 90-day rotating refresh tokens. See
  `docs/backend/auth.md` and ADR 0006.
- Swappable SMS backends: console (development), in-memory (tests), Africa's Talking (staging/production).
- `manage.py purge_otp_codes`, and a read-only admin page for sign-in codes.
- Every API error now uses the contract's `Error` shape `{code, message, fields}`.
- Profile endpoints `GET/PATCH /me/` with last-write-wins on the phone's `updated_at` (future timestamps count
  as now), and farm endpoints `GET/POST /farms/`, idempotent on `client_id`. Locations are rounded to 3 decimal
  places on the server too. See `docs/backend/profile-and-farms.md`.
- Diagnosis sync `POST /diagnoses/sync/`: batches of up to 25, one result per item (created, duplicate,
  conflict, invalid with errors keyed by payload path), each item in its own savepoint. Location is stored only
  with the farmer's consent. About 80 queries per full batch. See `docs/backend/diagnosis-sync.md` and ADR 0007.
- Advisory bundle `GET /advisory/bundle/?lang=`: published advice only, English fallback per disease (each entry
  says its `lang`), app messages (`uncertain`, `consult`, `rejected`, `no_advice`) editable in the admin with
  English defaults, content-hash `bundle_version` with ETag / 304. See `docs/backend/advisory-bundle.md` and
  ADR 0008.
- `manage.py load_sample_advice`: development-only placeholder advice for building the PWA.
- Model releases and `GET /model/latest/` (public; 404 `no_model` before the first release). `manage.py
  register_model` checks a converted model folder (shards present and at most 4 MB, at most 15 MB in total, labels
  identical to the backend's taxonomy, versioned https URL), computes size and SHA-256, and writes
  `manifest.json`. One release is current at a time; rollback is "make current" in the admin. See
  `docs/backend/model-releases.md` and ADR 0009.
- Feedback `POST /feedback/`: was a diagnosis right, and if not, what was it. Allowed on your own diagnoses, or on
  any diagnosis for extension-officer accounts; idempotent on `client_id` (201 / 200 / 409); append-only;
  self-reported `given_by_role` with the sending account always recorded. See `docs/backend/feedback.md` and
  ADR 0010.
- Diagnosis history `GET /diagnoses/`: the farmer's own diagnoses, newest first, cursor-paginated (100 per
  page), with `since` for catching up; 400 for a bad cursor or `since`. See `docs/backend/diagnosis-history.md`.
- Diagnosis photo `PUT /diagnoses/{client_id}/photo/`: raw JPEG up to 1 MB, only with `photo_consent` (403),
  only on your own synced diagnoses (404); sending again replaces it. EXIF (including GPS), XMP, IPTC and comments
  are stripped before storing. 400 `invalid_photo` for a body that isn't a JPEG, 415 for the wrong content type.
  See `docs/backend/diagnosis-photo.md` and ADR 0011.
- `ml/scripts/check_batch.py`: checks a batch of field photos and its `metadata.csv` before intake (columns,
  class ids, stage and zone values, field/farmer codes, GPS inside Zambia, dates, missing or extra photos, HEIC,
  too-small and duplicate photos) and counts photos per class. Template in `ml/templates/metadata.csv`. See
  `docs/ml/field-data.md` and ADR 0012.
- Contract tests: endpoint responses are validated against `docs/api-contract.yaml` (new dev dependency
  `jsonschema`).

### Fixed

- `PATCH /me/`: two quick edits without `updated_at` could land in the same clock tick, and the second one was
  silently ignored. Edits without a timestamp now always apply.

### Changed

- API contract 0.2.0: `POST /auth/otp/request/` can return 503 `sms_unavailable` when the SMS provider fails.
- API contract 0.2.0: `POST /farms/` is idempotent on `client_id`: 200 for a repeat from the same farmer, 409
  `conflict` if the id belongs to another farmer.
- API contract 0.3.0: `DiseaseAdvice.lang` (which language an advisory bundle entry is in, for English
  fallback); `AdvisoryBundle.ui` keys documented, including `no_advice`; `GET /model/latest/` returns 404
  `no_model` before the first release; `POST /feedback/` returns `FeedbackResult` `{id, client_id}` and 409
  `conflict`; `GET /diagnoses/` documents paging (100, newest first, exclusive `since`) and a 400 for a bad
  `cursor` or `since`.
- API contract 0.4.0: `PUT /diagnoses/{client_id}/photo/` adds 400 `invalid_photo` and 415
  `unsupported_media_type`, names the error codes for 403 and 413, and documents that a resend replaces the
  photo and that metadata is stripped.
- `docs/offline-sync.md` (0.3.0): queue flush order (profile, farms, diagnoses, feedback); duplicates keep the
  stored copy; what makes a sync batch a 400; server drops locations without consent.
- Field photo `metadata.csv` gains `field_id`, `farmer_code` and `notes`, so the dataset can be split by field
  and farmer; `stage` and `zone` now have fixed values (ADR 0012).
- CI runs the `ml/` scripts' tests and lint (they weren't run before).
- CI installs PWA dependencies with `npm ci` from the committed `package-lock.json`, with npm caching.
- `SECRET_KEY` must be at least 32 characters because it now signs JWTs. Update your local `backend/.env`
  (see `.env.example`). The CI and test keys were lengthened.

## [0.1.0] - 2026-10-15

### Added

- Project foundations (Build Step 1): README, CONTRIBUTING with branching and Definition of Done, PR template,
  pre-commit hooks, `.gitignore` that blocks datasets and model files, `docker-compose.yml` for PostGIS and Redis,
  and a CI workflow for the contract, backend and PWA.
- Draft API contract (Build Step 2): `docs/api-contract.yaml` (14 operations), `docs/model-output.md`,
  `docs/offline-sync.md` and the draft `docs/class-taxonomy.md` (19 classes).
- Backend: Django 5.2 + DRF skeleton with `GET /api/v1/health/` and OpenAPI docs at `/api/docs/`.
- PWA: Vite + Bootstrap shell that calls the health endpoint, and the tested prediction logic in
  `pwa/src/lib/prediction.js`.
- ML: `ml/labels.json` generated from the taxonomy, with tests.
- `pwa/package-lock.json` committed.

[Unreleased]: https://github.com/Elisha-11/Agri-Guard/compare/main...develop
[0.1.0]: https://github.com/Elisha-11/Agri-Guard/tree/main
