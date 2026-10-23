# 0016. Host model files on GitHub Pages for now; move to Cloudflare R2 later

- **Status:** Proposed (confirm at the Wednesday technical sync, then mark Accepted)
- **Date:** 2026-10-23
- **Deciders:** Elisha Lungu, Agness, Robert Ng'onga Chishangila

## Context

Phones download each model release (`model.json`, its shards, `labels.json`) from the URLs in the manifest that
`GET /model/latest/` returns ([ADR 0009](0009-model-releases.md)). The host must:

- serve over `https` (`register_model` refuses `http` outside development);
- send `Access-Control-Allow-Origin`, because the PWA loads the files from another origin;
- keep each version at its own path, `/models/<model_version>/`, that never changes
  ([model-output.md](../model-output.md) §1);
- be fast and cheap for farmers in Zambia. A release is about 8 MB (at most 15 MB). 1,000 farmers and two releases a
  month is about 16 GB of downloads a month.

The first release, baseline `2026.10.0`, was ready on 23 Oct 2026, and the PWA needs a real URL to build against. No
cloud account with a payment card, and no domain, is set up yet.

## Decision

Serve model files with **GitHub Pages from a separate public repo**,
[Elisha-11/agri-guard-models](https://github.com/Elisha-11/agri-guard-models), at
`https://elisha-11.github.io/agri-guard-models/models/<model_version>/`.

- A release is one commit adding one folder. A published folder is never changed or deleted.
- Model files are stored byte for byte (`.gitattributes`: `models/** -text`), so the SHA-256 the server recorded
  still matches.
- Elisha publishes (steps 2–5 of [model-releases.md](../backend/model-releases.md)).

## Alternatives considered

- **Cloudflare R2:** free downloads at any volume, 10 GB stored free, a Cloudflare location reportedly in Lusaka, and a private
  bucket could also hold diagnosis photos. Needs a payment card on file and, for production, a domain (its `r2.dev`
  address is rate-limited). This is the planned next host.
- **The same repo as the code (`Agri-Guard`):** would put binaries in the code history, which ignores model files
  on purpose, and every clone would grow by every release.
- **AWS S3 + CloudFront:** pays per GB downloaded; more setup than the team needs now.
- **Serving from our Django server:** no server is hosted yet, and the API would carry the heaviest traffic.

## Consequences

- Free, with nothing new to sign up for, and CORS (`Access-Control-Allow-Origin: *`) works by default.
- Limits: the published site may be at most 1 GB (about 60 releases at 15 MB) and has a soft limit of 100 GB of
  downloads a month. GitHub doesn't intend Pages for commercial products. Pages sets its own cache headers; that's
  fine because a version's URL never changes.
- **Move to R2 before a national rollout** or when downloads near 50 GB a month. Moving is cheap: new releases get
  the new base URL; old releases keep theirs while the Pages site stays up.
- Diagnosis photos can't go here (they're private). Their storage is still open.
