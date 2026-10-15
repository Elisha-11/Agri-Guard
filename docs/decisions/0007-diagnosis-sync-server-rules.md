# 0007. Server-side rules for diagnosis sync

- **Status:** Proposed (confirm at the Wednesday technical sync, then mark Accepted)
- **Date:** 2026-10-15
- **Deciders:** Elisha Lungu, Robert Ng'onga Chishangila

## Context

`docs/offline-sync.md` defines the four per-item results (created, duplicate, conflict, invalid). Building the
endpoint raised four questions it doesn't answer.

## Decisions

1. **An item without a valid UUID `client_id` fails the whole request (400).** Each result is reported against
   the item's `client_id`, and the contract's `SyncResult.client_id` must be a UUID. The PWA always generates one,
   so this only catches client bugs, and it catches them loudly.

2. **A duplicate is reported before validation, and the stored copy wins.** Diagnoses are append-only, so a
   resend, even a different or invalid one, never changes what's stored. The farmer's queue can then always drain.

3. **An unknown `farm_client_id` makes the item `invalid`; the PWA syncs farms first.** The alternative was to
   store the diagnosis without its farm. That would silently lose the link, which outbreak reports per farm need.
   Flushing the farm queue first is easy for the PWA to guarantee.

4. **Location is dropped unless the farmer's server-side profile has `location_consent`.** The phone is meant to
   ask before using GPS. The server enforces the same rule, so a client bug or an old app version can't store
   locations without consent. This follows the privacy principle in Zambia's Data Protection Act No. 3 of 2021:
   collect personal data only with consent.

## Alternatives considered

- **Report bad-`client_id` items as `invalid` with a made-up id:** breaks the contract's `SyncResult` schema.
- **Re-validate duplicates and report them invalid:** a stored diagnosis could then never leave the queue.
- **Accept location regardless of consent:** simpler, but trusts every client version with personal data.

## Consequences

- The PWA must order its queue: profile, then farms, then diagnoses (docs/backend/diagnosis-sync.md).
- If a farmer turns location on and the profile change syncs **after** their diagnoses, those diagnoses are stored
  without a location. That's an acceptable loss for a privacy guarantee.
- These rules are added to `docs/offline-sync.md` in the contract PR, so the PWA side sees them there too.
