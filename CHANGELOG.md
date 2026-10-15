# Changelog

All notable changes to AgriGuard are recorded here, newest first. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and versions follow [Semantic Versioning](https://semver.org/).

Every pull request adds a line under **Unreleased** in the right group (Added, Changed, Fixed, Removed, Security).
On release, Unreleased is renamed to the version and date, and `main` is tagged.

## [Unreleased]

### Added

- Documentation system: `docs/README.md` index, Architecture Decision Records in `docs/decisions/` (ADR 0001
  monorepo, ADR 0002 confidence thresholds), this changelog, and a Documentation section in CONTRIBUTING.

### Changed

- API contract 0.2.0: `POST /auth/otp/request/` can return 503 `sms_unavailable` when the SMS provider fails.
- CI installs PWA dependencies with `npm ci` from the committed `package-lock.json`, with npm caching.

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
