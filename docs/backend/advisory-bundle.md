# Advisory bundle: `GET /api/v1/advisory/bundle/?lang=…`

Everything the PWA needs to explain a diagnosis: each disease's name, symptoms, treatment, prevention and
follow-up advice, plus the fixed messages for uncertain or rejected results, all in one language. The PWA
downloads it once, keeps it offline, and checks for updates cheaply when it has signal. Design reasons are in
[ADR 0008](../decisions/0008-advisory-bundle-content-rules.md).

Code: `backend/apps/catalog/bundle.py` (content rules) and `views.py` (endpoint). Content is edited in the
Django admin under **Diseases and advice**.

## Request

```
GET /api/v1/advisory/bundle/?lang=ny
If-None-Match: "2026.10.15-f69006ac"        ← optional: the ETag of the copy the phone has
```

- **Public**, with no token, so a phone can fetch advice on first launch, before sign-in.
- `lang` is required: `en`, `ny` (Nyanja), `bem` (Bemba) or `toi` (Tonga). Anything else is a 400.

## Response

| Status | When | Body |
|--------|------|------|
| 200 | First download, or the content changed | The bundle (below), with an `ETag` header |
| 304 | `If-None-Match` matches the current version | Empty. Keep the cached copy |
| 400 | Missing or unknown `lang` | Contract `Error` |

Every response has `Cache-Control: no-cache`: the phone may keep the copy, but should check with the server
whenever it's online. With the ETag, that check costs a few hundred bytes.

```json
{
  "bundle_version": "2026.10.15-f69006ac",
  "lang": "ny",
  "taxonomy_version": "0.1",
  "diseases": [
    {
      "class_id": "maize__grey_leaf_spot",
      "lang": "en",
      "name": "Grey Leaf Spot",
      "local_name": null,
      "symptoms": ["Long grey rectangular spots between the leaf veins."],
      "treatment":  { "title": "…", "steps": ["…"], "audio_url": null },
      "prevention": { "title": "…", "steps": ["…"], "audio_url": null },
      "follow_up":  { "title": "…", "steps": ["…"], "audio_url": null },
      "safety_warning": "Wear gloves and a mask. Do not harvest for 14 days after spraying.",
      "reviewed_by": "Dr. …, ZARI",
      "reviewed_at": "2026-10-20"
    }
  ],
  "ui": {
    "uncertain": "We are not sure. Please take another photo.",
    "consult": "Please show this plant to an extension officer.",
    "rejected": "This photo is too dark, blurry or far away. …",
    "no_advice": "We recognised this problem, but advice for it has not been checked by an expert yet. …"
  }
}
```

## What goes in

- **Only published advice.** Advice can't be published until an agronomist is recorded under `reviewed_by` and
  `reviewed_at`; the database enforces it. Drafts never reach phones.
- **Language fallback, per disease.** Each disease uses the requested language if that version is published,
  otherwise the English one. `lang` on each entry says which one you got, so the app can, for example, choose
  the right voice for narration or label it "English only".
- **Missing diseases.** A disease with no published advice in the requested language or in English is left out.
  If the model predicts it, the PWA shows `ui.no_advice` (and no treatment).
- **Order** follows the model's class index (`ml/labels.json`).
- **Safety warnings.** Advice that involves any chemical must have one. The database enforces it, and the PWA
  must show it before the treatment steps.
- **`ui` messages** are edited in the admin (**App messages**). The English defaults come from
  `docs/model-output.md` §4. Other languages fall back to English message by message until translated.

## Versions and caching

`bundle_version` is `<date of the latest change>-<hash of the content>`, e.g. `2026.10.15-f69006ac`, and the ETag is
the same value in quotes. Any change (new advice, an edit, unpublishing, deleting, or a `ui` text change)
produces a new version. Nothing changing means the same version, however many times it's built. Each language has
its own version.

## For the PWA

1. On first launch, fetch the bundle for the farmer's language and store it in IndexedDB with its ETag.
2. When online (app open, `online` event), fetch again with `If-None-Match`. On 304 do nothing; on 200 replace
   the stored bundle.
3. When the farmer changes language, fetch that language's bundle. Keep English as well, in case a diagnosis
   needs it.
4. Look up a diagnosis's `class_id` in `diseases`. If it isn't there, show `ui.no_advice`.
5. For `status: uncertain` show `ui.uncertain`, for `consult` show `ui.consult`, and for a photo that failed the
   quality checks show `ui.rejected`.
6. The bundle is about 600 bytes per disease per language (11.6 KB for 19 diseases in sample data), small enough
   to precache.

## Writing advice (for agronomists and admins)

1. Admin → **Disease advice** → **Add**. Pick the disease and language.
2. Fill in the name, symptoms (one short sentence per line item), and the three sections. Each section has a
   title, a list of steps, and an optional `audio_url` for recorded narration.
3. If any step mentions a pesticide, fungicide or herbicide, tick **involves chemicals** and write the safety
   warning: protective equipment, dose, and the pre-harvest interval.
4. Once an agronomist has checked it, enter their name and the date in **reviewed by** and **reviewed at**,
   then tick **is published**. It's in the next bundle phones download.

## Sample data for development

Real advice doesn't exist yet. To build and test the app screens:

```powershell
python manage.py load_taxonomy
python manage.py load_sample_advice                  # English placeholders for all 19 classes
python manage.py load_sample_advice --all-languages  # plus ny / bem / toi placeholders
```

Every step reads `SAMPLE: …` and `reviewed_by` is `SAMPLE DATA - NOT FOR FARMERS`. The command refuses to run
unless `DEBUG` is on, so it can't touch a production database.

## Not built yet

- Recorded audio files (`audio_url`), planned for Step 12.
- Translations: Nyanja, Bemba and Tonga advice and `ui` messages need native-speaker translators and an agronomist
  review.
