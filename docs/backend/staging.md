# Staging server

Staging is a copy of the API on the internet for the team and the PWA to test against. It is **not for farmers**:
its data can be wiped, its SMS go to a simulator, and its advice is placeholder text. Why this setup:
[ADR 0017](../decisions/0017-staging-on-render-and-neon.md).

| Part | Where | Cost |
|------|-------|------|
| API (Django + gunicorn) | [Render](https://render.com) free web service, Frankfurt, from [`render.yaml`](../../render.yaml) | Free |
| Database (PostgreSQL) | [Neon](https://neon.tech) free project, AWS Frankfurt | Free |
| Sign-in SMS | [Africa's Talking](https://africastalking.com) sandbox: messages appear in its online phone simulator | Free |
| Model files | GitHub Pages ([ADR 0016](../decisions/0016-model-hosting-github-pages.md)) | Free |

Address: `https://agri-guard-staging.onrender.com` (Render adds a suffix if the name is taken; the dashboard shows the
real one). Health check: `/api/v1/health/`. API docs: `/api/docs/`. Admin: `/admin/`.

## What to expect

- **It sleeps.** After 15 minutes without requests Render stops the server; the next request wakes it and takes about
  a minute. The PWA should show a spinner, not an error, on a slow first request.
- **Diagnosis photos don't survive.** The free plan's disk is wiped on every deploy and restart. Everything in the
  database stays. Fine for testing uploads; production needs real photo storage (still open).
- **Every merge to `main` deploys.** Migrations and `load_taxonomy` run each time the server starts, before it
  accepts requests. If they fail, the deploy fails and the old version keeps running.
- Limits of the free plans: 750 server hours a month (enough for one service running all month), a small database,
  no backups. If staging data matters, it's in the wrong place.

## Setting it up (once)

Elisha does this, signed in to each service with GitHub.

1. **Database.** On Neon, create a project `agri-guard-staging`, region **AWS Europe Central 1 (Frankfurt)**,
   Postgres 16. Copy the connection string for the **direct** (not pooled) connection. It looks like
   `postgresql://<user>:<password>@<host>.eu-central-1.aws.neon.tech/neondb?sslmode=require`.
2. **SMS sandbox.** Sign up at Africa's Talking, open the **Sandbox** app, and generate an API key under
   **Settings → API Key**. The sandbox username is always `sandbox`.
3. **API.** On Render: **New → Blueprint**, pick the `Agri-Guard` repo. Render reads `render.yaml` and asks for the
   two secrets: `DATABASE_URL` (step 1) and `AFRICASTALKING_API_KEY` (step 2). `SECRET_KEY` is generated for you.
   The first deploy takes a few minutes; it's ready when `/api/v1/health/` returns `{"status": "ok", …}`.

Never put these secrets in the repo, an issue or a chat. They live in the Render dashboard and in your own `.env`.

## Running management commands on staging

The free plan has no shell, so run commands **from your laptop against the staging database**. Keep the Neon
string in a file outside the repo, typed without showing it on screen, so it never ends up in a commit, a
screenshot or a chat. Once, in PowerShell:

```powershell
$s = Read-Host "Neon connection string" -AsSecureString
[System.Net.NetworkCredential]::new("", $s).Password | Set-Content -NoNewline $HOME\.agriguard-staging-db
Remove-Variable s
```

Then, from `backend/`, each time. `DATABASE_URL` in the terminal overrides `.env`. If it's empty, commands silently
run against your **local** database instead, so check it first:

```powershell
$env:DATABASE_URL = Get-Content $HOME\.agriguard-staging-db
if ($env:DATABASE_URL -notlike "*.neon.tech/*") { Remove-Item Env:DATABASE_URL; throw "Not the Neon database" }
python manage.py createsuperuser          # your admin account: phone number + password
python manage.py load_sample_advice       # placeholder advice so the PWA has something to show
python manage.py register_model ..\ml\exports\2026.10.0 `
    --base-url https://elisha-11.github.io/agri-guard-models/models/2026.10.0/ --min-app-version 0.1.0 `
    --notes "Baseline: pipeline test only, not for farmers"
Remove-Item Env:DATABASE_URL              # back to your local database
```

These run with your laptop's development settings. `load_sample_advice` refuses to run with `DEBUG` off, so it never
runs on a deployed server; from a laptop it reaches whatever `DATABASE_URL` says. **Never point `DATABASE_URL` at
production like this.**

`register_model` rewrites `manifest.json` in the export folder; restore it from the models repo afterwards if needed.
On staging it's fine to make the baseline current (admin → Model releases → Make current), so the PWA can download
it; never on production.

## If something's wrong

| Symptom | Cause and fix |
|---------|---------------|
| Every address returns `Not Found` with header `x-render-routing: no-server` | Render isn't running a service at that address: still deploying, failed, or the name has a suffix. Check the service page |
| Deploy fails with `Set DATABASE_URL to PostgreSQL` | `DATABASE_URL` is blank in Render. Paste the Neon string in **Environment** |
| A command says `You have N unapplied migration(s)` against Neon | Staging isn't using that database. Compare Render's `DATABASE_URL` with your file |
| A connection string was shown on screen or pasted somewhere | Reset the password in Neon (**Roles → neondb_owner → Reset password**), then update Render and your file |

## Signing in on staging

1. Open the Africa's Talking sandbox **Launch Simulator** and enter a phone number, e.g. `+260971234567`.
2. Request a code: `POST /api/v1/auth/otp/request/` with that number (or from the PWA).
3. The SMS appears on the simulated phone. Send it to `POST /api/v1/auth/otp/verify/`.

Sandbox messages only reach numbers open in the simulator.

## Settings

Staging runs `config.settings.prod`, the same as production will, so problems show up here first. Only the
environment differs:

| Variable | Staging value | |
|----------|---------------|---|
| `DJANGO_SETTINGS_MODULE` | `config.settings.prod` | HTTPS only, secure cookies, real SMS backend required |
| `SECRET_KEY` | generated by Render | Also signs login tokens. Changing it signs everyone out |
| `DATABASE_URL` | Neon (secret) | |
| `RENDER_EXTERNAL_HOSTNAME` | set by Render | Added to `ALLOWED_HOSTS` automatically |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:5173` | Add the PWA's staging address when it has one |
| `SMS_BACKEND`, `AFRICASTALKING_*` | sandbox, username `sandbox`, key (secret) | |

Static files (the admin's CSS and JS) are collected at build time and served by WhiteNoise from gunicorn, with
hashed names and a one-year cache.

## Moving off the free plans

When the team needs staging always awake, or photos that survive restarts: Render Starter (no sleeping, a disk can
be attached) and Neon's paid plan (backups), or move both together with production. Revisit at the production
hosting decision.
