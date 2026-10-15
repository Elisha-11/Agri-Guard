# AgriGuard backend

Django 5.2 + Django REST Framework API for the AgriGuard PWA. It implements
[docs/api-contract.yaml](../docs/api-contract.yaml).

## Run it

Windows PowerShell (macOS/Linux: `source .venv/bin/activate` and `cp`):

```powershell
cd backend
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements\dev.txt
copy .env.example .env
python manage.py migrate
python manage.py load_taxonomy        # the 19 disease classes from ml/labels.json
python manage.py createsuperuser      # asks for a phone number, e.g. +260971234567
python manage.py runserver
```

| URL | What |
|-----|------|
| http://localhost:8000/api/v1/health/ | Liveness check |
| http://localhost:8000/api/docs/ | Interactive API docs, generated from the code |
| http://localhost:8000/admin/ | Django admin: farmers, diagnoses, and the advice text agronomists edit |

SQLite is the default. For PostgreSQL, run `docker compose up -d db` from the repo root, then set `DATABASE_URL` in
`.env` (see `.env.example`). CI always runs the tests on PostgreSQL.

## Check your work

Run the same checks CI runs before you push:

```powershell
ruff check .
black --check .
python manage.py makemigrations --check --dry-run
pytest
```

## Layout

```
backend/
├── config/
│   ├── settings/        base.py (shared), dev.py, test.py, prod.py
│   └── urls.py          /api/v1/, /api/schema/, /api/docs/, /admin/
├── apps/
│   ├── core/            health check, shared choices, validators, GeoPointMixin, test factories
│   ├── accounts/        Farmer (the user model, phone login)
│   ├── farms/           Farm
│   ├── catalog/         Disease, DiseaseAdvice, `load_taxonomy` command
│   └── diagnoses/       Diagnosis, Feedback
└── conftest.py          `taxonomy` fixture: the real 19 classes
```

What each model stores and which rules it enforces is in
[docs/backend/data-model.md](../docs/backend/data-model.md).

## Conventions

- **Contract first.** A field or enum the PWA sees must match `docs/api-contract.yaml`. Shared enums live in
  `apps/core/choices.py`, and `test_contract_alignment.py` fails if they drift.
- **Every model field has `help_text`.** It's the field's documentation, shown in the admin and the API docs.
- **Rules go in the database when possible** (`CheckConstraint`, `UniqueConstraint`), and in `clean()` otherwise.
  The API serializers call `full_clean()`.
- **Tests use the factories** in `apps/core/tests/factories.py`, and the `taxonomy` fixture whenever a disease is
  involved.
- **Synced records are append-only** and keyed by a client-generated `client_id` (docs/offline-sync.md).
