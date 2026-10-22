# 0015. Enforce reviews with CODEOWNERS (owner plus backup) and protect main

- **Status:** Proposed
- **Date:** 2026-10-22
- **Deciders:** Elisha Lungu, Agness, Robert Ng'onga Chishangila

## Context

The work plan says every pull request needs one approval from the owner of the code it touches, and `docs/` needs
all three of us. Until now this was only written in CONTRIBUTING, and every PR so far was merged without a required
review.

GitHub can enforce this with a `CODEOWNERS` file and branch protection, with two limits:

- An author's own approval never counts. If a folder lists only its owner, the owner's own PRs can never be approved.
- When a path lists several code owners, an approval from **any one** of them satisfies the rule. GitHub cannot
  require all of them.

## Decision

- Each folder in `.github/CODEOWNERS` lists its owner first and one backup: the person on the other side of that
  folder's interface (Robert for the backend, Elisha for `ml/`, Agness for `pwa/`, Robert for
  `pwa/src/inference/`).
- `main` requires a pull request, one approval from a code owner, the four CI jobs passing, resolved conversations,
  and no bypass for admins. Force pushes and deletions are off.
- `docs/` lists all three people, so all three are asked. "All three approve" stays a team rule, checked in the PR
  template.
- `develop` gets the same protection once the team decides whether PRs target `develop` or `main`.

## Alternatives considered

- **Owner only, no backup:** the owner could never get their own PRs approved.
- **Require two approvals on every PR:** with three people this means everyone approves everything, which is too slow
  for branches that live two or three days.
- **A CI job that counts approvals on `docs/` changes:** possible, but it needs a GitHub token and extra code for a
  rule that is easy to check by eye.

## Consequences

- PRs can no longer be merged without a second person; Elisha's own PRs need Robert or Agness.
- A change to someone else's folder can be approved by the backup instead of the owner. Reviewers should leave it for
  the owner unless the owner is away.
- Branch protection is a GitHub setting, not a file, so [repo-settings.md](../repo-settings.md) records exactly what
  to tick. Anyone changing it updates that page.
- A new teammate or a change of owner means updating CODEOWNERS, repo-settings.md and CONTRIBUTING together.
