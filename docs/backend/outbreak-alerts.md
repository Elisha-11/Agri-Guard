# Nearby outbreak alerts: `GET /api/v1/alerts/nearby/?lat=…&lng=…`

Tells a farmer which diseases several farms near them reported recently. Aggregate counts only. Design reasons
are in [ADR 0019](../decisions/0019-outbreak-alerts.md); the shape is `NearbyAlerts` in the contract (0.5.0).

Code: `backend/apps/alerts/` (`outbreaks.py` has the rules, `views.py` the endpoint).

## Request and response

```
GET /api/v1/alerts/nearby/?lat=-15.41&lng=28.29        (public, no token)
```

```json
{
  "generated_at": "2026-11-16T10:00:00Z",
  "radius_km": 10,
  "window_days": 7,
  "min_farms": 3,
  "alerts": [
    { "class_id": "maize__grey_leaf_spot", "farm_count": 5, "distance_band_km": 10, "window_days": 7 }
  ]
}
```

| Status | When |
|--------|------|
| 200 | Always for valid coordinates; `alerts` is empty when nothing crosses the threshold |
| 400 | `lat`/`lng` missing, not numbers, or outside Zambia (contract `Error`) |

`Cache-Control: no-cache`. Anonymous requests share the 60/min rate limit.

## Rules

1. **Counts:** located diagnoses of non-healthy classes that are `confident`, or confirmed by an extension
   officer (`Feedback.given_by_role = extension_officer`, `was_correct = true`). An officer's `was_correct = false`
   excludes the diagnosis. A farmer's own feedback never promotes an uncertain result.
2. **Window:** reporting time per `offline-sync.md` "Clock skew".
3. **Radius:** box filter in SQL, exact haversine distance in Python (no PostGIS point; ADR 0004).
4. **Each farm once** per disease; a diagnosis without a farm counts once per farmer.
5. **Only diseases with at least `min_farms` farms** appear, and only as counts.

## Settings

| Setting | Default | Environment variable |
|---------|---------|----------------------|
| Radius | 10 km | `OUTBREAK_RADIUS_KM` |
| Window | 7 days | `OUTBREAK_WINDOW_DAYS` |
| Minimum farms (also the privacy floor) | 3 | `OUTBREAK_MIN_FARMS` |

Don't set `OUTBREAK_MIN_FARMS` below 3: with one or two farms, a count can identify a household.

## Trying it locally

With the dev server running, three farms' confident diagnoses within 10 km in the last week make an alert. The
tests in `apps/alerts/tests/test_nearby_alerts.py` build exactly that and are the quickest way to see it work:

```bash
cd backend
pytest apps/alerts -q
```
