from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403

DEBUG = False
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30

# A deployed server must use PostgreSQL. Without DATABASE_URL, base.py falls back to SQLite, which on Render
# is a file on a disk wiped on every restart: the server would look healthy while losing all its data.
if DATABASES["default"]["ENGINE"] != "django.db.backends.postgresql":  # noqa: F405
    raise ImproperlyConfigured("Set DATABASE_URL to PostgreSQL; deployed servers can't use SQLite.")

# Render sets this to the service's address (agri-guard-staging.onrender.com); see docs/backend/staging.md.
RENDER_EXTERNAL_HOSTNAME = config("RENDER_EXTERNAL_HOSTNAME", default="")  # noqa: F405
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS = [*ALLOWED_HOSTS, RENDER_EXTERNAL_HOSTNAME]  # noqa: F405

# Admin CSS/JS, compressed and with hashed names so browsers can cache them forever (served by WhiteNoise).
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# Real SMS in production. The console backend would print farmers' sign-in codes into the server logs.
SMS_BACKEND = config("SMS_BACKEND", default="apps.accounts.sms.AfricasTalkingSmsBackend")  # noqa: F405
if SMS_BACKEND.endswith(("ConsoleSmsBackend", "LocmemSmsBackend")):
    raise ImproperlyConfigured("Production needs a real SMS backend; it would otherwise leak sign-in codes.")
