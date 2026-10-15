# Diagnosis history: `GET /api/v1/diagnoses/`

The farmer's own synced diagnoses, newest first. It's for **restoring history onto a new or reset phone**, and
for catching up when the farmer uses two devices. Uploading diagnoses is [diagnosis-sync.md](diagnosis-sync.md).

Code: `backend/apps/diagnoses/views.py` (`DiagnosisHistoryView`) and `pagination.py`. Needs an access token
([auth.md](auth.md)).

## Request

| Parameter | Notes |
|-----------|-------|
| `cursor` | Don't build it yourself: follow the `next` URL from the previous page |
| `since` | Optional ISO 8601 time. Only diagnoses **received** strictly after it. Pass the newest `received_at` the phone already has |

## Response

```json
{
  "next": "http://localhost:8000/api/v1/diagnoses/?cursor=cD0yMDI2LTEx…",
  "results": [
    {
      "id": "e39bbe75-85df-4f6e-a467-3fad34797706",
      "client_id": "9bfaeef0-1da0-44d3-b837-945359d90506",
      "farm_client_id": null,
      "crop": "cassava",
      "captured_at": "2026-11-04T10:00:00+02:00",
      "received_at": "2026-11-06T14:12:09.481220+02:00",
      "location": null,
      "prediction": {
        "class_id": "cassava__mosaic_disease",
        "class_index": 11,
        "confidence": 0.88,
        "status": "confident",
        "severity": "unknown",
        "top_k": [{ "class_id": "cassava__mosaic_disease", "confidence": 0.88 }],
        "model_version": "2026.11.0",
        "inference_ms": 2100
      },
      "app_version": "0.1.0",
      "has_photo": false
    }
  ]
}
```

- Each item is the contract's `Diagnosis`: exactly what the phone originally sent, plus `id`, `received_at` and
  `has_photo`.
- **100 per page**, newest first by `received_at`. `next` is `null` on the last page.
- `location` is `null` if the farmer hadn't consented when it synced (the server never stored it).
- Feedback isn't included.

| Status | When |
|--------|------|
| 200 | A page (possibly empty) |
| 400 | `since` isn't a date-time, or `cursor` is invalid (`fields` names which) |
| 401 | No valid token |

## Why a cursor, not page numbers

New diagnoses can arrive while a phone is restoring, for example synced from another device. With page numbers,
everything would shift, and the phone would see some items twice and miss others. A cursor remembers the
position, so every item is returned exactly once, even when many share the same `received_at` (a synced batch
lands in the same instant). Tests cover both cases.

## For the PWA

**Restore onto a new phone (after sign-in):**

1. `GET /diagnoses/`, then follow `next` until it's `null`.
2. Store each item by `client_id`. If one is already stored locally, keep the local copy: diagnoses never change.
3. Remember the largest `received_at` you've seen.

**Catch up later (second device):**

1. `GET /diagnoses/?since=<largest received_at stored>`, and follow `next` as above.
2. Update the stored largest `received_at`.

## Performance

One page costs 2 queries: the signed-in user, and the page itself with farms joined. A test fails if this grows.
