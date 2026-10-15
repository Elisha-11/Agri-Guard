# 0001. Keep ML, backend and PWA in one repository

- **Status:** Proposed (confirm at the Wednesday technical sync, then mark Accepted)
- **Date:** 2026-10-13
- **Deciders:** Elisha Lungu, Robert Ng'onga Chishangila

## Context

The System Development Plan called for three repositories (`agriguard-ml`, `agriguard-backend`, `agriguard-pwa`).
The team has one repository, `Elisha-11/Agri-Guard`. The three parts share a contract
(`docs/api-contract.yaml`, `labels.json`, the prediction format) that has to change in step.

## Decision

Use a single monorepo with top-level `ml/`, `backend/` and `pwa/` folders, plus `docs/` for the shared contract.
One CI workflow runs a separate job per folder.

## Alternatives considered

- **Three repositories, as planned:** a contract change would need three coordinated pull requests, and nothing would
  check that the backend and PWA agree on the same version.

## Consequences

- A contract change and the code that implements it land in one reviewed pull request.
- One issue tracker and one set of branch protections.
- CI runs all jobs on every PR, including folders that didn't change. That's acceptable at this size; path filters can
  be added later if CI gets slow.
