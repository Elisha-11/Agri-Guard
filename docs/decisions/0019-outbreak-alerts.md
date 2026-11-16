# 0019. Warn farmers about nearby outbreaks with aggregate counts only

- **Status:** Proposed (confirm at the Wednesday technical sync, then mark Accepted)
- **Date:** 2026-11-16
- **Deciders:** Robert Ng'onga Chishangila (for Elisha Lungu and Agness to confirm)

## Context

Diseases such as grey leaf spot and rust spread between neighbouring fields. A farmer who knows a disease is active
nearby can scout earlier. Every synced diagnosis can carry a location rounded to ~110 m (ADR 0004), stored only
with the farmer's consent (ADR 0007), so the server can see clusters.

Constraints:

- **Privacy.** Locations of individual farms are personal data under Zambia's Data Protection Act No. 3 of 2021.
  A map of who reported what could also stigmatise a farm or be used by buyers to discount a harvest.
- **A weak, early model.** The baseline (release 2026.10.0) is "pipeline test only". Unconfirmed low-confidence
  guesses must not raise alarms.
- **Repeat scans.** One worried farmer may photograph the same field many times.
- **Offline phones.** The warning must still show without signal.
- **No PostGIS point.** ADR 0004 stores locations as two decimal columns, to keep SQLite and Windows laptops working.

## Decision

`GET /api/v1/alerts/nearby/?lat=…&lng=…` (contract 0.5.0) returns, per disease, how many distinct farms within
a radius reported it during a recent window, and nothing else.

1. **Thresholds, in settings.** `OUTBREAK_RADIUS_KM = 10`, `OUTBREAK_WINDOW_DAYS = 7`, `OUTBREAK_MIN_FARMS = 3`,
   each overridable by environment variable. A disease is an alert only at or above `MIN_FARMS`.
2. **What counts.** A diagnosis with a location, for a non-healthy class, that the phone reported as `confident`
   (with that model release's own thresholds, ADR 0002), **or** that an extension officer confirmed. Uncertain and
   consult results count only after an officer confirms them; a farmer's own "correct" does not promote them.
   Any diagnosis an officer marked wrong is excluded. Rejected photos never reach the server.
3. **Deduplication.** Each farm counts once per disease per window. A diagnosis with no farm counts once per
   farmer. Ten scans of one field are one farm.
4. **Time.** The window uses the reporting time from `offline-sync.md` "Clock skew" (`captured_at` unless the device
   clock was clearly wrong, then `received_at`), computed in SQL.
5. **Distance.** A latitude/longitude box filters in SQL (works on SQLite and PostgreSQL), then the exact
   great-circle distance is checked in Python. No schema change; ADR 0004 stays in force.
6. **Privacy.**
   - The response holds only `class_id`, `farm_count`, `distance_band_km` and `window_days` per alert. No farm or
     farmer IDs, phone numbers, client IDs or coordinates; a test checks the raw response for them.
   - `MIN_FARMS` (3) is also a privacy floor: a disease reported by one or two farms is not mentioned at all,
     so a count can't point at a single household.
   - The distance band is the configured radius ("within 10 km"), not the distance to the nearest report.
   - The phone sends its own location rounded to 2 decimal places (~1 km), and only after the farmer taps
     "Turn on nearby alerts". Signing out clears the consent and the cached alerts.
7. **Public endpoint.** No sign-in, like the advisory bundle, so warnings work before sign-in. The anonymous rate
   limit (60/min) and the aggregate-only response limit what probing can learn.
8. **The app** caches the last response with its time and shows it offline as "last updated …". Each alert opens
   that disease's published advice (ADR 0008); alerts carry no advice text of their own. The alert is shown on the
   capture screen and, after a diagnosis of the same disease, on the result screen, and both can be read aloud.

## Alternatives considered

- **A map of individual reports (points or heatmap):** most informative, but it publishes where specific farms
  are and what they found. Not acceptable under the Data Protection Act without much more design.
- **District-level counts:** simple and private, but districts are large; a farmer at one edge would be warned
  about fields 80 km away and not about a neighbour across the district line.
- **Counting every diagnosis:** one farmer scanning repeatedly, or a run of bad photos, would raise false alarms.
- **Counting uncertain results too:** more sensitive, but with a baseline model it would mostly spread noise.
- **Return the nearest distance ("2 km away"):** more useful, but with small counts it narrows down a household.
- **GeoDjango `PointField` and a spatial index:** proper radius queries, but every developer would need GDAL/GEOS
  and PostgreSQL (the reason for ADR 0004). The box-then-exact approach is enough at MVP volumes.
- **Signed-in only:** blocks anonymous probing, but the app could not warn before sign-in, and real backend
  sign-in isn't wired into the app yet.

## Consequences

- Nothing real shows until the PWA's diagnosis sync queue sends diagnoses (docs/offline-sync.md). Once it does,
  call the alerts refresh after each sync as well as on app start and reconnect.
- Alert quality depends on the model; with the baseline, expect few confident results. Officer confirmations
  (feedback) become more valuable.
- The query reads every countable diagnosis in a ~20 km box for the window. If that grows large, add a composite
  index on `(latitude, longitude)` or move to a PostGIS point in a new ADR that supersedes ADR 0004.
- Not decided yet: whether an officer's correction (`corrected_disease`) should count toward the corrected
  disease; whether to send push or SMS alerts; and per-crop radii.
- Nyanja, Bemba and Tonga strings for the alert card are still to be translated by a native speaker (marked
  `_TODO_translate` in those locale files).
