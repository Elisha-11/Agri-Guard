# Feedback: `POST /api/v1/feedback/`

After a diagnosis, the farmer (or an extension officer checking the plant) says whether it was right, and if not,
what it really was. Each correction is a labelled example of a model mistake, the most valuable training data the
project gets. Design reasons are in [ADR 0010](../decisions/0010-feedback-rules.md).

Code: `backend/apps/diagnoses/views.py` (`FeedbackView`). Needs an access token ([auth.md](auth.md)).

## Request

```json
{
  "client_id": "5a1c…",
  "diagnosis_client_id": "9bfaeef0-1da0-44d3-b837-945359d90506",
  "was_correct": false,
  "corrected_class_id": "maize__common_rust",
  "comment": "Officer says rust, not grey leaf spot",
  "given_by_role": "extension_officer"
}
```

| Field | Required | Notes |
|-------|----------|-------|
| `client_id` | yes | UUIDv4 generated on the phone; the idempotency key |
| `diagnosis_client_id` | yes | The diagnosis's own `client_id`. It must be **synced already** |
| `was_correct` | yes | `true` / `false` |
| `corrected_class_id` | no | Only when `was_correct` is `false`. Must be a known class, e.g. `maize__common_rust` |
| `comment` | no | Up to 500 characters |
| `given_by_role` | no | `farmer` or `extension_officer`. Defaults to the signed-in account's role |

## Response

| Status | When | Body |
|--------|------|------|
| 201 | Stored | `{"id", "client_id"}` |
| 200 | This account already sent this `client_id`. The stored copy is kept as it was, even if the resend differs or is invalid | `{"id", "client_id"}` |
| 400 | Invalid; `fields` names the problem | Contract `Error` |
| 401 | No valid token | Contract `Error` |
| 409 | `conflict`: another account already used this `client_id` | Contract `Error` |

## Who can give feedback

- **A farmer**, on their own diagnoses.
- **An extension officer account** (`role: extension_officer`, set in the admin), on any diagnosis.
- **An officer using the farmer's phone:** send `given_by_role: "extension_officer"` from the farmer's account.
  That role is **self-reported**. The server also records which account sent it (`given_by`), so analysis can tell
  "officer account" from "farmer's phone, officer present".

A diagnosis that isn't synced yet, or that belongs to someone else (for a non-officer), gets the same 400 on
`diagnosis_client_id`. The API never reveals whether another farmer's diagnosis exists.

## Rules

- **Append-only.** Several feedback items on one diagnosis are all kept: the farmer says "correct", an officer later
  says "wrong, it's rust". Nothing is edited or replaced.
- `corrected_class_id` with `was_correct: true` is rejected; the database enforces this too.
- A correction may name a class from another crop, in case the farmer photographed the wrong crop.

## For the PWA

1. Put feedback at the **end** of the sync queue, after diagnoses (offline-sync.md). Feedback on an unsynced
   diagnosis fails.
2. Generate `client_id` when the farmer answers, and store it with the answer. Resending is always safe.
3. Treat 201 and 200 the same: it's stored. Move a 400 to the "could not sync" list. Report a 409 to Sentry.
4. Show the "what was it really?" picker only when the farmer says "wrong", using the same crop's classes from the
   advisory bundle first.

## Using feedback

Feedback is visible in the admin under **Diagnoses → Feedback**, and inline on each diagnosis. An export for the
ML pipeline (diagnosis, model version, predicted class, corrected class, role) is not built yet.
