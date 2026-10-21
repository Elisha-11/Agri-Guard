# 0009. Model releases: register with checks, one current release, rollback by switching

- **Status:** Proposed (confirm at the Wednesday technical sync, then mark Accepted)
- **Date:** 2026-10-15
- **Deciders:** Elisha Lungu, Robert Ng'onga Chishangila

## Context

`GET /model/latest/` tells every phone which model to run. If it points at a broken model, or at a model whose
class order doesn't match the backend, every farmer gets wrong results, and synced diagnoses are filed under the
wrong disease. Models are trained on Colab and uploaded to a CDN by hand, so mistakes are easy to make.

## Decisions

1. **Releases are created only by `manage.py register_model`, from the converted folder.** It checks the shards,
   the size limits and the labels against the backend's taxonomy, computes `size_bytes` and `sha256` itself, and
   writes `manifest.json`. The admin can't create releases by hand.
2. **"Latest" means "current", not "newest".** Exactly one release is current (a database constraint). Registering
   doesn't make a release current; that's a separate, deliberate step after uploading. Rolling back means making an
   older release current again.
3. **Each version has its own URL path** (`…/models/<version>/`), enforced by the command. A version is
   registered once and never overwritten.
4. **Thresholds are stored per release.** Calibration differs between models.
5. **404 `no_model` before the first release.** This is an additive contract change (0.3.0).

## Alternatives considered

- **Newest registered = latest:** a release registered before its files are uploaded would break every phone,
  and rolling back would mean deleting records.
- **Admin form for releases:** easy to type a wrong hash or size, and nothing would check the labels.
- **A config file or environment variable for the current model:** needs a deploy to roll back.

## Consequences

- Releasing takes three steps (register, upload, make current). That's deliberate.
- The upload is manual until a CDN is chosen. `register_model` could upload directly later.
