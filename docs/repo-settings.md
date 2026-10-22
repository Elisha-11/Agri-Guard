# GitHub repository settings

Code review is set up in two parts. [`.github/CODEOWNERS`](../.github/CODEOWNERS) is a file in the repo that says
who reviews which folder. The branch protection settings below live in GitHub's settings, not in the repo, so a
repo admin (Elisha) sets them by hand. Why it works this way is in
[ADR 0015](decisions/0015-code-owners-and-branch-protection.md).

## Who reviews what

| Folder | Owner | Backup reviewer |
|--------|-------|-----------------|
| `backend/`, `.github/`, `docker-compose.yml` | Elisha | Robert |
| `ml/` | Agness | Elisha |
| `pwa/` (except inference) | Robert | Agness |
| `pwa/src/inference/` | Agness | Robert |
| `docs/`, `CONTRIBUTING.md` | All three are asked; all three must approve by team rule | |
| Anything else (README, root files) | Any of the three | |

GitHub never counts an author's own approval. When the owner opens a PR on their own folder, the backup approves
it. When someone else changes a folder, the owner should approve it; GitHub also accepts the backup.

## Before turning protection on

1. Agness and Robert accept their collaborator invites (Settings → Collaborators, role **Write**).
2. Agness's GitHub username replaces `@TODO-agness` in `.github/CODEOWNERS` (Robert is
   `@robertngongachishangila-creator`).
3. GitHub shows no errors on the CODEOWNERS file (open it on github.com; problems appear in a banner above it).

## Protect `main`

On github.com: **Settings → Branches → Add branch protection rule** (or **Add classic branch protection rule**),
branch name pattern `main`. Tick:

- [x] **Require a pull request before merging**
  - [x] Require approvals: **1**
  - [x] Dismiss stale pull request approvals when new commits are pushed
  - [x] **Require review from Code Owners**
- [x] **Require status checks to pass before merging**. Search for and add all four CI jobs (they appear after CI
      has run once on a PR):
  - `API contract is valid OpenAPI`
  - `ML scripts lint + tests`
  - `Backend lint + tests`
  - `PWA lint + tests + build`
- [x] **Require conversation resolution before merging**
- [x] **Do not allow bypassing the above settings** (this includes admins, so nobody merges their own PR unreviewed)
- [ ] Allow force pushes: leave **off**
- [ ] Allow deletions: leave **off**

Click **Create**.

## Protect `develop`

The plan protects `develop` the same way. Our pull requests currently go to `main`, and `develop` has fallen behind
it, so the team first decides which branch PRs target. Once `develop` is in use again, add a second rule with the
same ticks and the pattern `develop`.

## Check it works

Open a small PR that changes a file in `backend/`. GitHub should request a review from Elisha and Robert, show the
four checks, and keep **Merge** disabled until one of them approves and the checks pass.
