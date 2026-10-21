"""Fill every disease with PLACEHOLDER advice, so the PWA can be built and tested before real advice exists.

    python manage.py load_sample_advice            # English only
    python manage.py load_sample_advice --all-languages

The text is deliberately not agronomic advice: every step says SAMPLE and "reviewed_by" says it isn't for
farmers. It refuses to run unless DEBUG is on, so it can't reach a production database. Real advice is written
and reviewed by an agronomist in the admin (docs/backend/advisory-bundle.md).
"""

from datetime import date

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.catalog.models import Disease, DiseaseAdvice
from apps.core.choices import Language

REVIEWER = "SAMPLE DATA - NOT FOR FARMERS"


def section(title):
    return {"title": f"{title} (sample)", "steps": [f"SAMPLE: {title.lower()} step 1.", "SAMPLE: step 2."],
            "audio_url": None}  # fmt: skip


class Command(BaseCommand):
    help = "Development only: create placeholder advice for every disease."

    def add_arguments(self, parser):
        parser.add_argument("--all-languages", action="store_true", help="Also create ny, bem and toi rows.")

    def handle(self, *args, all_languages, **options):
        if not settings.DEBUG:
            raise CommandError("Refusing to load sample advice with DEBUG off. It must never reach farmers.")
        if not Disease.objects.exists():
            raise CommandError("No diseases yet. Run `manage.py load_taxonomy` first.")

        langs = Language.values if all_languages else [Language.ENGLISH]
        count = 0
        for disease in Disease.objects.all():
            condition = disease.class_id.split("__", 1)[1].replace("_", " ").capitalize()
            for lang in langs:
                DiseaseAdvice.objects.update_or_create(
                    disease=disease,
                    lang=lang,
                    defaults={
                        "name": f"{condition} [{lang}]" if lang != "en" else condition,
                        "symptoms": ["SAMPLE: what the farmer would see."],
                        "treatment": section("Treatment"),
                        "prevention": section("Prevention"),
                        "follow_up": section("Follow-up"),
                        "involves_chemicals": False,
                        "reviewed_by": REVIEWER,
                        "reviewed_at": date.today(),
                        "is_published": True,
                    },
                )
                count += 1
        self.stdout.write(self.style.WARNING(f"Loaded {count} SAMPLE advice rows. Not for farmers."))
