# Offline Sync Rules (contract v0.1.0)

The PWA must work with **no connectivity for days**. Diagnoses are created on the device and pushed to the server
later. The server is never required for a diagnosis to happen.

## Identity

- Every diagnosis gets a **client-generated UUIDv4** (`client_id`) at the moment of capture.
- `client_id` is the idempotency key. Sending the same `client_id` twice never creates two rows.

## Queue (PWA, IndexedDB store `sync_queue`)

- Every new diagnosis and every feedback item is appended to the queue.
- Flush when: the app opens online, the `online` event fires, or Background Sync fires (where supported).
- Batch size: up to **25 items** per `POST /api/v1/diagnoses/sync/`.
- Retry with exponential backoff: 30 s, 2 min, 10 min, 1 h, then hourly. Reset on success.
- On metered connections, photos are **not** uploaded unless the farmer allows it in Settings. Diagnosis metadata
  (a few hundred bytes) always syncs.
- The UI shows a "pending sync: N" count while the queue is non-empty.

## Server behaviour per item

| Situation | Server action | Per-item result `status` |
|-----------|---------------|--------------------------|
| New `client_id` | Create diagnosis | `created` |
| Known `client_id`, same owner | No change. Return existing server id. | `duplicate` |
| Known `client_id`, different owner | Reject | `conflict` |
| Fails validation (unknown `class_id`, bad coordinates, …) | Reject that item only | `invalid` + `errors` |

The batch always returns **HTTP 200** with one result per item, in order, unless the whole request is malformed
(400) or unauthenticated (401). The PWA removes `created` and `duplicate` items from the queue, keeps `invalid` items
for inspection in a "could not sync" list, and logs `conflict` to Sentry.

## Conflict policy

Diagnoses are **append-only**. A farmer cannot edit the model's prediction after the fact, so there are no edit
conflicts. Corrections ("this was wrong, it is actually X") are separate `Feedback` records, which are also
append-only and keyed by their own `client_id`.

Profile edits use **last-write-wins** on `updated_at` (client timestamp, server clamps future timestamps to now).

## Clock skew

`captured_at` is the device clock and may be wrong. The server stores it as sent and also records `received_at`.
Reporting uses `captured_at` unless it is more than 30 days after `received_at` or before 2026-01-01, in which case
`received_at` is used.

## Location and privacy

- GPS is **optional** and requires explicit consent on first use.
- Coordinates are rounded on the device to **3 decimal places (~110 m)** before storage or sync. That is enough for
  district-level outbreak mapping without pinpointing a homestead.
