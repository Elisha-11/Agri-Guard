"""The advisory bundle: every disease name and its advice for one language, downloaded once and cached
offline by the PWA. Contract `GET /advisory/bundle/` and schema `AdvisoryBundle`. Rules
(docs/backend/advisory-bundle.md, ADR 0008):

- Only **published** advice is included, and publishing requires an agronomist review (catalog/models.py).
- For each disease, the requested language is used if published, otherwise English, marked with its `lang`.
  A disease with no published advice in either is left out; the PWA then shows the `no_advice` message.
- `ui` messages fall back to English key by key, the same way.
- `bundle_version` and the ETag are derived from the content, so they change exactly when the content does,
  including when advice is unpublished or deleted.
"""

import hashlib
import json

from apps.core.choices import Language

from .models import Disease, DiseaseAdvice, UiMessage

FALLBACK_LANG = Language.ENGLISH


def _nullable(text):
    return text or None


def _section(section):
    return {"title": section["title"], "steps": list(section["steps"]), "audio_url": section.get("audio_url")}


def disease_entry(advice):
    """Contract `DiseaseAdvice`, plus `lang`: which language this entry is actually in."""
    return {
        "class_id": advice.disease_id,
        "lang": advice.lang,
        "name": advice.name,
        "local_name": _nullable(advice.local_name),
        "symptoms": list(advice.symptoms),
        "treatment": _section(advice.treatment),
        "prevention": _section(advice.prevention),
        "follow_up": _section(advice.follow_up),
        "safety_warning": _nullable(advice.safety_warning),
        "reviewed_by": advice.reviewed_by,
        "reviewed_at": advice.reviewed_at.isoformat(),
    }


def _content_version(content, latest):
    digest = hashlib.sha256(json.dumps(content, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    date = latest.strftime("%Y.%m.%d") if latest else "0000.00.00"
    return f"{date}-{digest[:8]}"


def build_bundle(lang):
    """Return the contract `AdvisoryBundle` for `lang` (a Language value)."""
    langs = [lang] if lang == FALLBACK_LANG else [lang, FALLBACK_LANG]
    published = DiseaseAdvice.objects.filter(is_published=True, lang__in=langs).select_related("disease")
    by_disease = {}
    for advice in published:
        current = by_disease.get(advice.disease_id)
        if current is None or advice.lang == lang:
            by_disease[advice.disease_id] = advice

    entries = [by_disease[d.class_id] for d in Disease.objects.all() if d.class_id in by_disease]
    ui = {}
    ui_rows = list(UiMessage.objects.filter(lang__in=langs))
    for message in sorted(ui_rows, key=lambda m: m.lang != FALLBACK_LANG):  # English first, then overridden
        ui[message.key] = message.text

    taxonomy_versions = sorted(set(Disease.objects.values_list("taxonomy_version", flat=True)))
    content = {
        "lang": lang,
        "taxonomy_version": taxonomy_versions[-1] if taxonomy_versions else "",
        "diseases": [disease_entry(a) for a in entries],
        "ui": ui,
    }
    latest = max((row.updated_at for row in [*entries, *ui_rows]), default=None)
    return {"bundle_version": _content_version(content, latest), **content}


def etag_for(bundle):
    """Strong ETag. bundle_version already covers the whole content."""
    return f'"{bundle["bundle_version"]}"'
