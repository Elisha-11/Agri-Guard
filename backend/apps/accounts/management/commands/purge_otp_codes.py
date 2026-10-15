"""Delete SMS sign-in codes older than a day. Schedule it daily in production (cron or Celery beat).

    python manage.py purge_otp_codes
    python manage.py purge_otp_codes --days 7

Old codes are useless (they expire after 10 minutes) and only matter briefly for rate limiting and support.
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.accounts.models import OtpCode


class Command(BaseCommand):
    help = "Delete SMS sign-in codes older than --days (default 1)."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=1)

    def handle(self, *args, days, **options):
        deleted, _ = OtpCode.objects.filter(created_at__lt=timezone.now() - timedelta(days=days)).delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted {deleted} sign-in code(s) older than {days} day(s)."))
