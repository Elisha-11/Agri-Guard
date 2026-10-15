# Profile and farms endpoints

The signed-in farmer's own profile (`/me/`) and farms (`/farms/`). Both need an access token from
[sign-in](auth.md): `Authorization: Bearer <access>`. Without one, or with an expired or invalid one, the response
is 401, and the PWA should refresh the token or send the farmer back to sign-in.

Code: `backend/apps/accounts/views.py` (`MeView`) and `backend/apps/farms/views.py` (`FarmListView`).

## `GET /api/v1/me/`

Returns the contract's `Farmer`:

```json
{
  "id": "f70ce96d-41f6-4379-a4ea-1937f76bf3df",
  "phone": "+260961234567",
  "display_name": "Mrs Phiri",
  "preferred_language": "bem",
  "province": null,
  "district": "Kasama",
  "role": "farmer",
  "photo_consent": false,
  "location_consent": false,
  "updated_at": "2026-10-15T13:57:42.757726+02:00"
}
```

Text fields the farmer hasn't filled in are `null`, never `""`.

## `PATCH /api/v1/me/`

Send only the fields that changed, plus `updated_at`, the time the farmer made the edit on the phone:

```json
{ "district": "Kasama", "preferred_language": "bem", "updated_at": "2026-10-12T08:15:00+02:00" }
```

| Field | Notes |
|-------|-------|
| `display_name`, `province`, `district` | Text, or `null` to clear |
| `preferred_language` | `en`, `ny`, `bem`, `toi` |
| `photo_consent`, `location_consent` | `true` / `false` |
| `updated_at` | Optional. Omit it if the edit is happening online right now |

`phone` and `role` can't be changed here. They are ignored if sent.

**Last-write-wins.** The phone may send an edit made offline days ago. It's applied only if its `updated_at` is
newer than the server's. Otherwise it's ignored, so an old edit can't undo a newer one made on another phone.
A timestamp in the future (a phone clock running fast) is treated as "now".

The response is always the server's **current** profile, whether or not the edit was applied. The PWA should
overwrite its local copy with it. That's how a phone whose edit lost catches up.

| Status | When |
|--------|------|
| 200 | Profile returned (edit applied or ignored as stale) |
| 400 | Invalid value; `fields` names it |
| 401 | No valid token |

## `GET /api/v1/farms/`

The farmer's own farms, sorted by name, as a plain array (no pagination; a farmer has a handful at most).

```json
[
  {
    "id": "4215d7d0-eb00-481d-8454-27a704ee05cc",
    "client_id": "4607914f-2063-4499-9cac-c6d288d32c60",
    "name": "Dambo plot",
    "crops": ["cassava"],
    "size_hectares": null,
    "location": { "lat": -10.213, "lng": 31.18 }
  }
]
```

## `POST /api/v1/farms/`

```json
{
  "client_id": "4607914f-2063-4499-9cac-c6d288d32c60",
  "name": "Dambo plot",
  "crops": ["cassava"],
  "size_hectares": 0.75,
  "location": { "lat": -10.213, "lng": 31.18 }
}
```

Only `client_id` (a UUIDv4 generated on the phone when the farm is created) and `name` are required.

**Idempotent on `client_id`**, because the sync queue may send the same farm twice:

| Status | When |
|--------|------|
| 201 | New farm created |
| 200 | This farmer already sent this `client_id`; the existing farm is returned **unchanged** (later edits in a retry are ignored) |
| 400 | Invalid; `fields` names the problem (`client_id`, `name`, `crops`, `size_hectares` or `location`) |
| 401 | No valid token |
| 409 | `conflict`: the `client_id` belongs to another farmer. Generate a new UUID and resend |

Validation:

- `crops`: only `maize`, `groundnut`, `cassava`, `soybean`, `cotton`, without repeats.
- `size_hectares`: zero or more, up to 2 decimal places; `null` if unknown.
- `location`: `{"lat", "lng"}` inside Zambia (lat −18.1 to −8.2, lng 21.9 to 33.8), or `null`. **The server rounds
  to 3 decimal places (~110 m)**, even if the phone sent more, so a precise homestead location is never stored.

Editing and deleting farms aren't in the contract yet.

## For the PWA

- Store the farm locally with its `client_id` first and show it straight away, then queue the POST. Treat 201 and 200
  the same: the farm is on the server.
- Round GPS to 3 decimals on the phone too, before storing it locally. The server rounding is a safety net, not
  the main privacy measure.
- After `PATCH /me/`, replace the local profile with the response.

## How these are tested

`apps/accounts/tests/test_profile_api.py` and `apps/farms/tests/test_farms_api.py` call the endpoints with a real
JWT (the `farmer_api` fixture). Every response body is checked against the schema in `docs/api-contract.yaml`
with `assert_matches_contract()`, so a field that drifts from the contract fails the build.
