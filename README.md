# AgriGuard AI

**Intelligent crop disease detection and farmer advisory platform for Zambian smallholder farmers.**

A farmer photographs a leaf, and an on-device AI model returns the disease name, a confidence score, a severity
band and a three-part advisory (immediate treatment, prevention, follow-up). It works fully offline, in English,
Nyanja, Bemba and Tonga, with voice narration.

Submitted under the **iHub Innovation Programme** · Lusaka, Zambia · MVP window October–December 2026.

| Role | Owner | Folders |
|------|-------|---------|
| API & infrastructure: Django, database, sign-in, sync, advisory content, servers, CI/CD, security | Elisha Lungu | `backend/`, `.github/` |
| ML & model delivery: images, labelling, training, conversion, in-app inference | Agness | `ml/`, `pwa/src/inference/` |
| PWA & field UX: screens, camera, offline storage and sync queue, languages, voice, field testing | Robert Ng'onga Chishangila | rest of `pwa/` |

---

## Repository layout

This is a single monorepo. The development plan called for three repositories (`agriguard-ml`, `agriguard-backend`,
`agriguard-pwa`); they live here as top-level folders, which keeps the API contract and the code that implements it in
the same pull request.

```
Agri-Guard/
├── docs/                    All documentation; start at docs/README.md
│   ├── api-contract.yaml    OpenAPI 3.1 spec: the source of truth for every endpoint
│   ├── model-output.md      Shape of a prediction, severity bands, confidence thresholds
│   ├── offline-sync.md      Sync payload, idempotency and conflict rules
│   ├── class-taxonomy.md    DRAFT crop/disease class list, pending agronomist sign-off
│   └── decisions/           Architecture Decision Records: why things are the way they are
├── CHANGELOG.md             What changed in each release
├── ml/                      Dataset tooling, training, evaluation, conversion (Agness)
├── backend/                 Django 5 + DRF + PostGIS API (Elisha)
├── pwa/                     Vite + Bootstrap 5 + TensorFlow.js PWA (Robert; src/inference/ is Agness)
└── .github/workflows/       CI for backend, PWA and the contract
```

## Quick start

Prerequisites: **Python 3.11+**, **Node 20+**, **Docker** (for PostgreSQL/PostGIS and Redis), **Git**.

```bash
git clone https://github.com/Elisha-11/Agri-Guard.git
cd Agri-Guard
git checkout develop

# one-time: install git hooks (ruff, black, prettier, eslint, yaml checks)
pip install pre-commit && pre-commit install
```

### Backend (http://localhost:8000)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements/dev.txt
cp .env.example .env
python manage.py migrate
python manage.py load_taxonomy        # the 19 disease classes from ml/labels.json
python manage.py runserver
# check: http://localhost:8000/api/v1/health/  and  http://localhost:8000/api/docs/
pytest
```

The default `.env` uses SQLite so you can start without Docker. To run against PostGIS and Redis as production will:

```bash
docker compose up -d db redis       # from the repo root
# then in backend/.env set DATABASE_URL=postgres://agriguard:agriguard@localhost:5432/agriguard
```

More detail (admin login, layout, conventions) is in [backend/README.md](backend/README.md).

### PWA (http://localhost:5173)

```bash
cd pwa
npm install
npm run dev
npm test
```

### ML

See [`ml/README.md`](ml/README.md). Training runs on Google Colab; datasets and model artefacts are versioned with DVC
and are **never** committed to Git.

## Where we are

Tracking against the [System Development Plan](docs/) (14 build steps, 7 milestones). Who does which task, and by
when, is in the [work plan](docs/AgriGuard_Work_Plan.pdf) (snapshot of 21 Oct 2026).

| Milestone | Due | Status |
|-----------|-----|--------|
| M1: API contract, Figma screens, class taxonomy signed off | 14 Oct 2026 | Contract and taxonomy drafted, awaiting review and agronomist sign-off |
| M2: 6,000+ field images collected | 28 Oct 2026 | Not started |
| M3: Dataset v1 + baseline model | 11 Nov 2026 | Not started |
| M4: ≥85% test accuracy, model < 15 MB on CDN | 25 Nov 2026 | Not started |
| M5: Full offline PWA | 9 Dec 2026 | Not started |
| M6: Field validation | 23 Dec 2026 | Not started |
| M7: Public MVP release | 31 Dec 2026 | Not started |

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md). In short: branch from `develop`, use Conventional Commits, document the change in
the same PR ([docs/README.md](docs/README.md) is the index, [CHANGELOG.md](CHANGELOG.md) gets a line), and every PR needs
approval from the owner of the code it touches (changes to `docs/` need all three) plus green CI.
