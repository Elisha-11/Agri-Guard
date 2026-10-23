# 0017. Run staging on Render's free plan with a Neon database and the Africa's Talking sandbox

- **Status:** Proposed (confirm at the Wednesday technical sync, then mark Accepted)
- **Date:** 2026-10-23
- **Deciders:** Elisha Lungu, Agness, Robert Ng'onga Chishangila

## Context

The PWA needs a real API on the internet to test against: sign-in, sync, the advisory bundle and model downloads.
Nothing was hosted yet. Staging is for the team, not farmers, so it can be slow to wake and lose uploaded photos,
but it should run the same settings as production (`config.settings.prod`) so problems show up early. No cloud
account with a payment card is set up. The backend is Django 5.2 with PostgreSQL; it needs no Redis or workers yet.

## Decision

- **API:** a Render free web service in Frankfurt (closest Render region to Zambia), defined in `render.yaml` and
  deployed on every merge to `main`. Migrations and `load_taxonomy` run at start, since the free plan has no
  pre-deploy step.
- **Database:** a Neon free project in AWS Frankfurt. Render's own free database is deleted after 30 days.
- **SMS:** the Africa's Talking sandbox. It exercises the real SMS code path; messages appear in its simulator.
- **Static files:** WhiteNoise serves the admin's CSS and JS from gunicorn.
- **One-off commands** (`createsuperuser`, `register_model`, `load_sample_advice`) run from a laptop with
  `DATABASE_URL` pointed at Neon, because the free plan has no shell.

## Alternatives considered

- **Render paid (about $7–13 a month):** always awake, with backups. Needs a card; not worth it for staging yet.
- **Railway ($5 a month):** simple, but has no free tier and needs a card.
- **A VPS (about $5 a month):** cheapest always-on option, but we would maintain the OS, HTTPS and backups.
- **SMS codes in the server log:** simpler, but doesn't test the Africa's Talking integration, and production
  settings rightly refuse log-only backends.

## Consequences

- Costs nothing and needs no card.
- The server sleeps after 15 minutes idle; the first request then takes about a minute. The PWA must handle a slow
  first request.
- Uploaded diagnosis photos are lost on every deploy or restart (ephemeral disk). Production photo storage is still
  open.
- The free plans have no backups. Staging data is disposable.
- Revisit when choosing production hosting, which will need an always-on server, backups and photo storage.
