# Diagnosis sync: `POST /api/v1/diagnoses/sync/`

How diagnoses made on the phone, often days earlier and offline, reach the server. The general rules are in the
contract's [offline-sync.md](../offline-sync.md). This page covers exactly what the backend does with each item,
the error format, and what the PWA needs to do. Design reasons are in
[ADR 0007](../decisions/0007-diagnosis-sync-server-rules.md).

Code: `backend/apps/diagnoses/sync.py` (rules), `serializers.py` (validation), `views.py` (endpoint).
Needs an access token ([auth.md](auth.md)).

## Request

Up to **25** items, in the order they were captured:

```json
{
  "items": [
    {
      "client_id": "9bfaeef0-1da0-44d3-b837-945359d90506",
      "farm_client_id": null,
      "crop": "cassava",
      "captured_at": "2026-11-04T10:00:00+02:00",
      "location": { "lat": -13.633, "lng": 32.65 },
      "prediction": {
        "class_id": "cassava__mosaic_disease",
        "class_index": 11,
        "confidence": 0.88,
        "status": "confident",
        "severity": "unknown",
        "top_k": [
          { "class_id": "cassava__mosaic_disease", "confidence": 0.88 },
          { "class_id": "cassava__healthy", "confidence": 0.1 }
        ],
        "model_version": "2026.11.0",
        "inference_ms": 2100
      },
      "app_version": "0.1.0"
    }
  ]
}
```

Optional: `farm_client_id`, `location`, `app_version`, `prediction.inference_ms`.

## Response

Always **200**, with one result per item, **in the same order**:

```json
{
  "results": [
    { "client_id": "9bfaeef0-…", "status": "created", "id": "e39bbe75-…" },
    { "client_id": "9bfaeef0-…", "status": "duplicate", "id": "e39bbe75-…" },
    { "client_id": "8add3348-…", "status": "invalid", "id": null,
      "errors": { "prediction.class_id": ["cassava__mosaic_disease is not a maize class."] } }
  ]
}
```

| `status` | Meaning | `id` | What the PWA does |
|----------|---------|------|-------------------|
| `created` | Stored | server id | Remove from the queue |
| `duplicate` | Already stored for this farmer (an earlier sync, a retry, or the same item twice in this batch). **The stored copy is kept as it was**; nothing in the resend is applied | server id | Remove from the queue |
| `conflict` | That `client_id` belongs to **another** farmer. Their record is never revealed | `null` | Log to Sentry; keep the item. It's a bug (bad UUID generation, or a cloned phone) |
| `invalid` | Failed validation; `errors` says why | `null` | Move to the "could not sync" list |

The whole request fails, and nothing is stored, only if the envelope itself is wrong:

| Status | When |
|--------|------|
| 400 | `items` missing, not a list, empty, more than 25, or an item without a valid UUID `client_id` (its result couldn't be reported) |
| 401 | No valid token |

## Validation

`errors` keys are paths into the item as sent, e.g. `crop`, `location`, `prediction.class_id`,
`prediction.top_k.0.confidence`.

| Rule | Error on |
|------|----------|
| `crop` is one of the five contract crops | `crop` |
| `captured_at` is an ISO 8601 date-time | `captured_at` |
| `prediction.class_id` is a known class (from `ml/labels.json`) | `prediction.class_id` |
| …and belongs to the item's `crop` | `prediction.class_id` |
| `prediction.class_index` matches that class | `prediction.class_index` |
| `confidence` and every `top_k[].confidence` are 0–1 | `prediction.confidence`, `prediction.top_k.N.confidence` |
| `status` is `confident` / `uncertain` / `consult` | `prediction.status` |
| `severity` is `none` for healthy classes, and only for them | `prediction.severity` |
| `top_k` has 1–3 known classes, highest first, and `top_k[0]` is the prediction | `prediction.top_k` |
| `farm_client_id`, if given, is one of **this farmer's synced** farms | `farm_client_id` |
| `location`, if kept (see below), is `{lat, lng}` inside Zambia | `location` |

Retired classes are still accepted, because phones running an older model may still predict them.

The server doesn't check `status` against the confidence thresholds. Those belong to the model version that ran on
the phone (docs/model-output.md §4).

## Order: sync farms first

A diagnosis can name a farm by `farm_client_id`, but only a farm the server already has. **Flush the farm queue
(`POST /farms/`) before the diagnosis queue.** Otherwise the diagnosis comes back `invalid` on `farm_client_id`.

## Location

- Stored only if the farmer's profile has `location_consent: true` **on the server**. Without it, the location
  is dropped and the diagnosis is still `created`. So if a farmer turns location on, sync the profile change
  (`PATCH /me/`) before the diagnoses.
- Always rounded to 3 decimal places (~110 m), whatever the phone sent.

## Clock skew

`captured_at` is stored as sent, and `received_at` is the server's time. Reports use `Diagnosis.reported_at`, which
falls back to `received_at` when the phone's clock was clearly wrong (see [data-model.md](data-model.md)).

## Performance

A full batch of 25 costs about 80 database queries: 3 per item (savepoint, insert, release) plus a few to load the
farmer's farms, the disease list and any already-stored `client_id`s. A test fails if this grows.

## PWA checklist

1. Queue order: profile edits, then farms, then diagnoses, then feedback.
2. Send up to 25 diagnoses per request, oldest first.
3. Match results to queue items by position (or `client_id`).
4. Remove `created` and `duplicate`. Move `invalid` to the "could not sync" list, with its `errors`. Report
   `conflict` to Sentry.
5. On a network error or 5xx, keep everything and retry with the backoff in offline-sync.md. Resending is always
   safe.

## Not built yet

- `GET /diagnoses/`: history, for restoring onto a new phone.
- `PUT /diagnoses/{client_id}/photo/`: photo upload.
