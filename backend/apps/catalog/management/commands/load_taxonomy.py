"""Load or update Disease rows from ml/labels.json.

    python manage.py load_taxonomy                 # uses ../ml/labels.json
    python manage.py load_taxonomy path/to/labels.json

Safe to run repeatedly. It refuses changes that break the taxonomy rules in docs/class-taxonomy.md: a class
id moving to a different index, two ids sharing an index, or a class disappearing instead of being marked
retired. Any of those would silently change the meaning of diagnoses already stored.
"""

import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.catalog.models import Disease

DEFAULT_LABELS = Path(settings.BASE_DIR).parent / "ml" / "labels.json"


class Command(BaseCommand):
    help = "Create or update diseases from ml/labels.json (idempotent; refuses to reorder classes)."

    def add_arguments(self, parser):
        parser.add_argument("labels", nargs="?", default=str(DEFAULT_LABELS), help="Path to labels.json")

    def handle(self, *args, labels, **options):
        path = Path(labels)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            version = data["taxonomy_version"]
            classes = data["classes"]
        except (OSError, ValueError, KeyError) as exc:
            raise CommandError(f"Can't read a taxonomy from {path}: {exc}") from exc

        indices = [c["index"] for c in classes]
        if len(indices) != len(set(indices)):
            raise CommandError("Two classes in labels.json share an index.")

        existing = {d.class_id: d for d in Disease.objects.all()}
        incoming_ids = {c["id"] for c in classes}

        missing = sorted(set(existing) - incoming_ids)
        if missing:
            raise CommandError(
                f"Classes missing from labels.json: {', '.join(missing)}. "
                "Mark them retired instead of removing them."
            )
        for c in classes:
            old = existing.get(c["id"])
            if old and old.class_index != c["index"]:
                raise CommandError(
                    f"{c['id']} moved from index {old.class_index} to {c['index']}. "
                    "Indices are fixed forever."
                )

        created = updated = 0
        with transaction.atomic():
            for c in classes:
                disease = existing.get(c["id"]) or Disease(class_id=c["id"], class_index=c["index"])
                is_new = disease.class_id not in existing
                disease.crop = c["crop"]
                disease.is_healthy = c["is_healthy"]
                disease.is_retired = c.get("retired", False)
                disease.taxonomy_version = version
                disease.full_clean(validate_unique=is_new)
                disease.save()
                created += is_new
                updated += not is_new

        self.stdout.write(
            self.style.SUCCESS(f"Taxonomy {version}: {created} created, {updated} updated, from {path}.")
        )
