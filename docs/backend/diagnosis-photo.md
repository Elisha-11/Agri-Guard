# Diagnosis photo: `PUT /api/v1/diagnoses/{client_id}/photo/`

Attaches the leaf photo to a diagnosis the farmer has already synced. It's optional: only farmers who turned on
photo sharing (`photo_consent`) can upload, and the photos are used for retraining the model and for expert
review. Design reasons are in [ADR 0011](../decisions/0011-diagnosis-photo-rules.md).

Code: `backend/apps/diagnoses/views.py` (`DiagnosisPhotoView`) and `backend/apps/diagnoses/photos.py` (JPEG
check and metadata stripping). Needs an access token ([auth.md](auth.md)).

## Request

```http
PUT /api/v1/diagnoses/9bfaeef0-1da0-44d3-b837-945359d90506/photo/
Authorization: Bearer <access token>
Content-Type: image/jpeg

<JPEG bytes, at most 1 MB>
```

The body is the raw JPEG, not a form upload. `{client_id}` is the diagnosis's own `client_id`.

## Response

| Status | Code | When |
|--------|------|------|
| 204 | | Stored. Sending again replaces it |
| 400 | `invalid_photo` | The body is empty, not a JPEG, cut off, or has no image in it |
| 401 | | No valid token |
| 403 | `photo_consent_required` | The farmer hasn't turned on photo sharing |
| 404 | `not_found` | No synced diagnosis with this `client_id` for this farmer |
| 413 | `photo_too_large` | Over 1 MB (1,048,576 bytes) |
| 415 | `unsupported_media_type` | `Content-Type` isn't `image/jpeg` |

Errors use the contract `Error` shape. The checks run in this order: consent, then diagnosis, then body. A phone
without consent gets its 403 before the photo is read.

## Rules

- **Your own diagnoses only.** Another farmer's diagnosis gets the same 404 as an unsynced one. Extension-officer
  accounts can't upload to other farmers' diagnoses.
- **Sending again replaces the photo**, so retrying is always safe. There is one file per diagnosis.
- **Metadata is removed before storing:** EXIF (including GPS), XMP, IPTC and comments. The image data, colour
  profile and JFIF header are kept unchanged. This keeps a farmer's location off the server unless they agreed to
  `location_consent`.
- After an upload, `has_photo` is `true` in `GET /diagnoses/` ([diagnosis-history.md](diagnosis-history.md)).

## Where photos are stored

In Django's default file storage under `diagnoses/<farmer id>/<client_id>.jpg`. On a server that is `MEDIA_ROOT`
(`backend/media/`, ignored by git). They are **not** served at a public URL. Staff can see whether a diagnosis
has a photo in the admin.

Turning photo sharing **off** later doesn't delete photos already uploaded. That is an open decision, see
ADR 0011.

## For the PWA

1. Upload photos **after** the diagnosis has synced (a 404 means "sync first"), and only on Wi-Fi unless the
   farmer allowed mobile data (offline-sync.md).
2. Check `photo_consent` on the phone before queuing a photo. If the server still answers 403, drop the photo
   from the queue; don't retry.
3. Resize on a canvas and export with `canvas.toBlob(cb, "image/jpeg", quality)`. That draws the photo upright
   and drops EXIF. Aim well under 1 MB.
4. Treat 204 as done. Retry network errors and 5xx later. Drop the photo on 400, 413 or 415 and report them to
   Sentry: they mean a bug in the resize step.
