# Model Output Format (contract v0.1.0)

This is the agreement between the model (Developer A) and the PWA inference layer (Developer B). The PWA never
interprets raw tensors itself. It only uses `labels.json` and the rules below.

## 1. Files published with every model version

Published to a versioned CDN path: `/models/<model_version>/`

| File | Purpose |
|------|---------|
| `model.json` + `group*-shard*.bin` | TensorFlow.js graph model, sharded (≤ 4 MB per shard) for progressive download |
| `labels.json` | Index → class metadata (see below). Index order is fixed forever. |
| `manifest.json` | Same object as `GET /api/v1/model/latest/` returns, so the PWA can verify offline |

### `labels.json`

```json
{
  "model_version": "2026.11.0",
  "taxonomy_version": "0.1",
  "input": { "width": 224, "height": 224, "channels": 3, "preprocessing": "efficientnet", "value_range": [0, 255] },
  "classes": [
    { "index": 0, "id": "maize__healthy", "crop": "maize", "is_healthy": true },
    { "index": 1, "id": "maize__northern_leaf_blight", "crop": "maize", "is_healthy": false }
  ]
}
```

- `preprocessing: "efficientnet"` means the Keras EfficientNet preprocessing is **inside** the model graph. The PWA
  feeds raw RGB pixels as float32 in `[0, 255]`, shape `[1, 224, 224, 3]`. No normalisation in JavaScript.
- Human-readable names are **not** in `labels.json`. They come from the advisory bundle, per language, keyed by `id`.

## 2. Raw model output

A single tensor of shape `[1, N]`: softmax probabilities summing to 1, where `N = classes.length`.

## 3. Prediction object (what the PWA builds and stores)

The PWA turns the raw output into this object. It is stored in IndexedDB and is exactly the `prediction` field sent
in the sync payload (`Prediction` schema in `api-contract.yaml`).

```json
{
  "class_id": "maize__grey_leaf_spot",
  "class_index": 2,
  "confidence": 0.91,
  "status": "confident",
  "severity": "moderate",
  "top_k": [
    { "class_id": "maize__grey_leaf_spot", "confidence": 0.91 },
    { "class_id": "maize__northern_leaf_blight", "confidence": 0.06 },
    { "class_id": "maize__common_rust", "confidence": 0.02 }
  ],
  "model_version": "2026.11.0",
  "inference_ms": 1840
}
```

| Field | Type | Rule |
|-------|------|------|
| `class_id` | string | `top_k[0].class_id` |
| `class_index` | int | index of the top class in `labels.json` |
| `confidence` | float 0–1, 2 dp | top-1 probability **after** calibration (temperature scaling baked into the model in Step 6) |
| `status` | enum | see §4 |
| `severity` | enum | `none` · `low` · `moderate` · `high` · `unknown`; see §5 |
| `top_k` | array, length 3 | sorted descending |
| `model_version` | string | from `labels.json` |
| `inference_ms` | int | shutter-to-result time on device (target ≤ 5000 ms on 1 GB RAM) |

## 4. Confidence thresholds → `status`

| Condition | `status` | What the farmer sees |
|-----------|----------|----------------------|
| confidence ≥ **0.70** | `confident` | Disease name, severity, full advisory |
| 0.40 ≤ confidence < 0.70 | `uncertain` | "We are not sure. Please take another photo." Tips on light/distance, then top-2 candidates |
| confidence < **0.40** | `consult` | "Please show this plant to an extension officer." No treatment advice shown |
| image failed quality checks (blur, dark, too small) | `rejected` | Retake prompt; inference not run |

These thresholds are **initial values**. Developer A re-tunes them in Step 6 from the calibration curve on the
validation set and updates this table in a contract PR. The PWA must read them from `manifest.json`
(`thresholds.confident`, `thresholds.uncertain`), not hard-code them.

## 5. Severity

`healthy` classes always return `severity: "none"`.

**Open decision (needs agronomist input from `class-taxonomy.md` Q5):** how severity is produced in the MVP.

- **Option A (recommended for MVP):** the farmer answers one icon-based question on the result screen ("How much of
  the field looks like this? A few plants / About half / Most of it"), mapped to `low` / `moderate` / `high`. No extra
  labelling, and it works on day one.
- **Option B:** label severity stage (early/mid/advanced) during expert review in Label Studio and train a second
  output head. More accurate per-leaf, but it doubles the labelling cost in Weeks 3–5.

Until decided, the PWA sends `severity: "unknown"` for disease classes.
