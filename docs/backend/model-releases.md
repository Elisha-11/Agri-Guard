# Model releases and `GET /api/v1/model/latest/`

How a trained model gets from Colab onto farmers' phones, and how to roll it back. Design reasons are in
[ADR 0009](../decisions/0009-model-releases.md). The files a model ships with are defined in the contract's
[model-output.md §1](../model-output.md).

Code: `backend/apps/releases/` (`models.py`, `views.py`, `management/commands/register_model.py`).

## The endpoint

`GET /api/v1/model/latest/` is **public** (no token). The PWA calls it whenever it's online.

| Status | Body |
|--------|------|
| 200 | The **current** release's manifest (contract `ModelManifest`) |
| 404 | `{"code": "no_model", …}`: no release is current yet. The app should say diagnosis isn't available yet |

```json
{
  "model_version": "2026.11.0",
  "taxonomy_version": "0.1",
  "model_url": "https://elisha-11.github.io/agri-guard-models/models/2026.11.0/model.json",
  "labels_url": "https://elisha-11.github.io/agri-guard-models/models/2026.11.0/labels.json",
  "size_bytes": 9437326,
  "sha256": "327d257f947d1743c966481a5a05116eeb3d3e4a937debbb5848ff61506d97e6",
  "thresholds": { "confident": 0.7, "uncertain": 0.4 },
  "min_app_version": "0.1.0"
}
```

It's sent with `Cache-Control: no-cache`, so after a rollback no phone keeps a stale answer.

## Releasing a model, step by step

Agness (ML owner) does step 1 and hands over the folder; Elisha (backend and hosting) does steps 2–5. Model files
are hosted on GitHub Pages from the [agri-guard-models](https://github.com/Elisha-11/agri-guard-models) repo
([ADR 0016](../decisions/0016-model-hosting-github-pages.md)).

1. **Convert** the trained model to TensorFlow.js with 4 MB shards, into a folder named after the version, e.g.
   `2026.11.0/`. Put that model's `labels.json` in the same folder, with `"model_version": "2026.11.0"`.
2. **Register it.** This checks the folder and writes `manifest.json` into it:
   ```powershell
   python manage.py register_model path\to\2026.11.0 `
       --base-url https://elisha-11.github.io/agri-guard-models/models/2026.11.0/ `
       --min-app-version 0.1.0 `
       --confident 0.7 --uncertain 0.4 `
       --notes "EfficientNet-B0, dataset v1.2, test accuracy 87.4%"
   ```
3. **Publish** the whole folder, `manifest.json` included, in a clone of `agri-guard-models`:
   ```bash
   cp -r path/to/2026.11.0 models/
   git add models/2026.11.0
   git commit -m "release: 2026.11.0"
   git push
   ```
   Never change or delete a folder that's already published; a fix is a new version. The repo's `.gitattributes`
   keeps the files byte for byte, so the SHA-256 still matches.
4. **Check** that `model_url` and `labels_url` open in a browser. Pages takes a few minutes to publish.
5. **Make it current:** admin → **Model releases** → tick it → action **Make the selected release current**. Phones
   switch the next time they're online. (`--make-current` in step 2 does this immediately, but only use it if the
   files are already uploaded.)

### What `register_model` refuses

It records nothing and writes nothing if:

| Problem | Why it matters |
|---------|----------------|
| A shard listed in `model.json` is missing | Phones would fail half-way through the download |
| A shard is over 4 MB, or the total is over 15 MB | Progressive download on slow connections; phone storage (contract limit) |
| `labels.json` has another `model_version` or `taxonomy_version` | It's the wrong labels file |
| `labels.json` classes differ from the backend's, even by one index | Every synced diagnosis would be filed under the wrong disease |
| The version is already registered | A version is published once; cached copies are never overwritten |
| `--base-url` isn't `https://…/<version>/` | Each version must live at its own path ([model-output.md](../model-output.md) §1) |
| Thresholds outside 0–1, or `uncertain` ≥ `confident` | The app's result logic would break |

If the model was trained on a new taxonomy, update `docs/class-taxonomy.md` and `ml/labels.json`, run
`manage.py load_taxonomy`, then register.

## Rolling back

Admin → **Model releases** → tick the older release → **Make current**. Only one release can be current; the
database enforces it, and the switch is atomic. Phones go back to the older model the next time they check.

## Thresholds

`thresholds.confident` and `thresholds.uncertain` decide `confident` / `uncertain` / `consult`
([model-output.md §4](../model-output.md)). They're stored per release, because each model's calibration differs.
The defaults (0.7 / 0.4) come from ADR 0002; Step 6 sets real values from the calibration curve.

## Trying a release on a laptop before publishing it

With `DEBUG=True`, `register_model` accepts an `http://` base URL, so the whole chain runs locally, without
publishing anything. Use a version you won't publish, or delete the local release before registering it for real:

From the repo root, each in its own terminal where it says so:

```bash
# 1. export (ML venv)                                                       → ml/exports/2026.10.0/
C:\tf\Scripts\python ml/scripts/export_tfjs.py ml/runs/<run>/saved_model

# 2. register against a local URL and make it current (development database only)
cd backend
python manage.py register_model ../ml/exports/2026.10.0 \
    --base-url http://localhost:8001/2026.10.0/ --min-app-version 0.1.0 \
    --notes "Baseline: pipeline test only, not for farmers" --make-current

# 3. serve ml/exports with CORS (own terminal, repo root)
npx http-server@14.1.1 ml/exports -p 8001 --cors

# 4. run the API (own terminal, backend/)
python manage.py runserver 8000
```

`GET http://localhost:8000/api/v1/model/latest/` then returns the manifest, and the PWA dev server can download the
model. Use `--cors`: the PWA runs on another port, so the browser blocks the download without it (Python's
`http.server` doesn't send CORS headers; it's fine for `curl`, not for the app).

`ml/exports/` and the database are git-ignored, so each developer registers on their own machine. Only make a
baseline current in a development database, never on staging or production.

## Release log

| Version | Date | Where | What | Current? |
|---------|------|-------|------|----------|
| 2026.10.0 | 23 Oct 2026 | [GitHub Pages](https://elisha-11.github.io/agri-guard-models/models/2026.10.0/model.json); registered in a development database only | Baseline EfficientNet-B0 from run `real-photos-300`: 300 public photos (maize healthy, northern leaf blight, grey leaf spot, common rust; soybean healthy), random split, 84.4% on 45 test photos. 8.0 MB in 2 shards, `model.json` SHA-256 `0af3a9ed…91fa`. Loaded in TF.js 4.22.0 and labelled 15 sample photos correctly. Pipeline test only, not for farmers | Locally only |

## For the PWA

1. Call `/model/latest/` when online. On 404 `no_model`, show "diagnosis not available yet".
2. If `min_app_version` is newer than the app, ask the farmer to update the app first. Don't download.
3. If `model_version` differs from the cached model, download `model.json` and its shards (from the same folder),
   check the SHA-256 of `model.json` against `sha256`, then swap. Keep the old model until the new one is verified.
4. Store the manifest with the model and use its `thresholds`. Never hard-code them.

## Not built yet

- Publishing from `register_model`. For now it's a manual commit to `agri-guard-models`.
- Moving to Cloudflare R2 (ADR 0016) before a national rollout.
- Where diagnosis photos are stored in production.
- A URL reachability check before making a release current.
