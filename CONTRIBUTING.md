# Contributing to AgriGuard AI

## Branches

| Branch | Purpose |
|--------|---------|
| `main` | Always deployable. Production releases are tagged here (`v0.1.0`, …). Only `develop` and `hotfix/*` merge in. |
| `develop` | Integration branch. All feature work merges here first. |
| `feature/<short-name>` | One branch per task, e.g. `feature/camera-capture`, `feature/diagnosis-sync`. Deleted after merge. |
| `hotfix/<short-name>` | Branched from `main` for urgent production fixes; merged back into `main` **and** `develop`. |

Prefix feature branches with the area when useful: `feature/ml-augmentation`, `feature/api-otp`, `feature/pwa-i18n`.

## Commits: Conventional Commits

```
<type>(<scope>): <summary in imperative mood>

feat(api): add diagnosis sync endpoint
fix(pwa): stop camera stream when leaving capture screen
docs(contract): add severity band to prediction schema
chore(ci): cache pip downloads
test(api): cover duplicate client_id on sync
```

Types: `feat`, `fix`, `docs`, `chore`, `test`, `refactor`, `perf`, `ci`. Scopes: `ml`, `api`, `pwa`, `contract`, `ci`, `infra`.

## Pull requests

1. Open the PR against `develop` and fill in the template.
2. CI must be green (lint, tests, build).
3. **The owner of the code it touches must approve.** Elisha owns `backend/` and `.github/`, Agness owns `ml/` and
   `pwa/src/inference/`, Robert owns the rest of `pwa/`. Changes to `docs/` need all three. No self-merges, including
   for docs.
4. Squash-merge, delete the branch.

## Changing the contract

`docs/api-contract.yaml`, `docs/model-output.md` and `docs/offline-sync.md` are the agreement between the backend, the
model and the PWA. A change to any of them:

- goes in its own PR with the `contract` scope (`docs(contract): …` or `feat(contract): …`),
- must be approved by **all three** owners,
- bumps `info.version` in `api-contract.yaml` (minor for additive changes, major for breaking ones).

## Definition of Done

A task is done only when **all** of these are true:

- [ ] Merged to `develop` through a reviewed, approved PR.
- [ ] Automated tests cover the new behaviour and the whole suite passes in CI.
- [ ] Lint and format checks pass with no suppressed warnings.
- [ ] Verified on a real low-end Android device (UI work), not only a desktop browser.
- [ ] Offline behaviour considered and either implemented or explicitly deferred in writing in the PR.
- [ ] User-facing text added to all four translation files (en, ny, bem, toi).
- [ ] README / API docs / user guide updated in the same PR.

## Documentation

Everything we build is documented **in the same pull request** as the code. A reviewer should reject a PR that
changes behaviour without updating the docs.

| You changed… | Update |
|--------------|--------|
| Anything a user, teammate or reviewer would notice | A line under **Unreleased** in [CHANGELOG.md](CHANGELOG.md) |
| An endpoint, a payload or the prediction format | `docs/api-contract.yaml` / `model-output.md` / `offline-sync.md` (contract PR rules above) |
| Backend models, apps or settings | [backend/README.md](backend/README.md) and [docs/backend/](docs/backend/) |
| PWA screens, storage or service worker | `pwa/README.md` and `docs/pwa/` |
| Datasets, training or model conversion | [ml/README.md](ml/README.md) and the model card for that version |
| A design choice someone might later ask "why?" about | A new ADR in [docs/decisions/](docs/decisions/) (copy `0000-template.md`) |
| Any new document | Add it to the index in [docs/README.md](docs/README.md) |

In code:

- Every module, class and public function has a docstring that says **why** it exists, not just what it does.
- Every Django model field has `help_text`. It shows in the admin and in the generated API docs.
- Comments explain non-obvious decisions and link the contract section or ADR they follow.

## Data and model files

Images, datasets and trained models are versioned with **DVC**, never committed as raw binaries. `.gitignore`
blocks the common formats, so if `git add` refuses a file, that's intentional.

## Weekly rhythm

| When | What |
|------|------|
| Daily 08:30 | 10-min stand-up (WhatsApp/call): yesterday, today, blockers |
| Monday | Sprint planning (60 min) |
| Wednesday | Technical sync (45 min): architecture, contract changes |
| Friday | Demo and retrospective (60 min): a step is closed only when its exit condition is shown here |
