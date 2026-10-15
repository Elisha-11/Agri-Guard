from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403

DEBUG = False
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30

# Real SMS in production. The console backend would print farmers' sign-in codes into the server logs.
SMS_BACKEND = config("SMS_BACKEND", default="apps.accounts.sms.AfricasTalkingSmsBackend")  # noqa: F405
if SMS_BACKEND.endswith(("ConsoleSmsBackend", "LocmemSmsBackend")):
    raise ImproperlyConfigured("Production needs a real SMS backend; it would otherwise leak sign-in codes.")
