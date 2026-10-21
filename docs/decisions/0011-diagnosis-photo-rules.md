# 0011. Diagnosis photos: owner only, replace on resend, strip metadata on the server

- **Status:** Proposed (confirm at the Wednesday technical sync, then mark Accepted)
- **Date:** 2026-10-21
- **Deciders:** Elisha Lungu, Robert Ng'onga Chishangila

## Context

`PUT /diagnoses/{client_id}/photo/` lets a farmer who has turned on `photo_consent` send the leaf photo behind a
diagnosis, for retraining and expert review. The contract fixes the format (JPEG, at most 1 MB, resized on the
phone) and the 403 / 404 / 413 responses. It doesn't say what a resend does, whether officers can upload, or what
happens to the file's metadata.

Phone cameras write EXIF into every JPEG, often including **GPS coordinates**. If those were stored, a farmer
who said no to `location_consent` would still have their field's location on the server.

## Decisions

1. **Only the diagnosis's owner can upload.** Another farmer's diagnosis gets the same 404 as one that isn't
   synced, as for feedback (ADR 0010). Extension-officer accounts can't upload either: the photo comes from the
   phone that took it.
2. **Sending again replaces the photo.** `PUT` means "this is the photo", so a retry after a dropped connection is
   always safe. The stored file name is fixed per diagnosis, so there is only ever one file.
3. **The server strips metadata from every photo** (EXIF, XMP, IPTC, comments), even though the PWA's canvas
   resize normally drops it already. Colour profile and JFIF segments are kept.
4. **The JPEG is checked by its structure in plain Python**, not decoded with Pillow. A file that isn't a JPEG,
   is cut off, or has no image in it is a 400 `invalid_photo`. No new dependency, and the photo is never
   re-encoded, so no quality is lost.
5. **The check order is consent (403), then diagnosis (404), then body (415, 413, 400).** A phone without consent
   is turned away before its photo is read.
6. **Photos go to Django's default file storage** (`MEDIA_ROOT` on the server's disk for now) under
   `diagnoses/<farmer id>/<client_id>.jpg`. They are **not** served at a public URL. Moving to object storage
   later is a settings change.

## Alternatives considered

- **Reject a second upload with 409:** a retry after a timeout, where the first upload actually arrived, would
  look like an error on the phone.
- **Trust the PWA to strip EXIF:** one browser or code change away from storing GPS without consent.
- **Decode and re-save with Pillow:** catches more broken files, but adds a dependency with a history of
  image-parsing CVEs and costs quality on every photo.

## Consequences

- A structurally valid JPEG with garbage image data is accepted. The ML pipeline must skip photos it can't decode.
- Dropping EXIF also drops the orientation tag. Canvas-resized photos are already upright, but a photo sent
  without the PWA's resize may be stored rotated.
- Two new error responses (400 `invalid_photo`, 415) need a contract change (0.4.0).
- **Open: what happens to photos when a farmer turns `photo_consent` off.** For now they are kept. Deleting
  them, or excluding them from training, is a privacy decision for the team and possibly ZARI. It needs a
  follow-up ADR before photos are used for training.
