"""Settings shared by every environment. Secrets and URLs come from the environment (.env locally)."""

from datetime import timedelta
from pathlib import Path

import dj_database_url
from decouple import Csv, config

BASE_DIR = Path(__file__).resolve().parent.parent.parent

APP_VERSION = "0.1.0"

SECRET_KEY = config("SECRET_KEY")
DEBUG = config("DEBUG", default=False, cast=bool)
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="localhost,127.0.0.1", cast=Csv())

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # third party
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "drf_spectacular",
    "corsheaders",
    # local
    "apps.core",
    "apps.accounts",
    "apps.farms",
    "apps.catalog",
    "apps.diagnoses",
    "apps.releases",
]

# Farmers sign in with phone + SMS code, so the user model is keyed on phone (ADR 0003).
# This must stay set from the very first migration; changing it later means rebuilding the database.
AUTH_USER_MODEL = "accounts.Farmer"

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# SQLite by default so a fresh clone runs without Docker.
# PostgreSQL/PostGIS (docker compose up -d db) is set through DATABASE_URL.
DATABASES = {
    "default": dj_database_url.parse(
        config("DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}"),
        conn_max_age=60,
        # Neon suspends an idle database after a few minutes; check a kept connection before reusing it.
        conn_health_checks=True,
    )
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en"
TIME_ZONE = "Africa/Lusaka"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CORS_ALLOWED_ORIGINS = config("CORS_ALLOWED_ORIGINS", default="http://localhost:5173", cast=Csv())

REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.AnonRateThrottle"],
    "DEFAULT_THROTTLE_RATES": {"anon": "60/min"},
    # Every error body uses the contract's Error shape {code, message, fields}.
    "EXCEPTION_HANDLER": "apps.core.exceptions.exception_handler",
}

# Tokens (ADR 0006). Farmers can be offline for weeks, so refresh tokens are long-lived; each one works once
# (rotation + blacklist), so a stolen refresh token stops working as soon as the farmer's phone uses its copy.
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=config("JWT_ACCESS_MINUTES", default=60, cast=int)),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=config("JWT_REFRESH_DAYS", default=90, cast=int)),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": False,  # apps.accounts.otp updates it on sign-in instead
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# SMS sign-in codes (apps/accounts/otp.py, docs/backend/auth.md). Values match the contract's descriptions.
OTP_TTL_SECONDS = 10 * 60
OTP_MAX_REQUESTS = 3
OTP_REQUEST_WINDOW_SECONDS = 15 * 60
OTP_MAX_ATTEMPTS = 5

# Where SMS go. The console backend prints codes in the runserver window (development only).
SMS_BACKEND = config("SMS_BACKEND", default="apps.accounts.sms.ConsoleSmsBackend")
AFRICASTALKING_USERNAME = config("AFRICASTALKING_USERNAME", default="")
AFRICASTALKING_API_KEY = config("AFRICASTALKING_API_KEY", default="")
AFRICASTALKING_SENDER_ID = config("AFRICASTALKING_SENDER_ID", default="")
AFRICASTALKING_SANDBOX = config("AFRICASTALKING_SANDBOX", default=False, cast=bool)

SPECTACULAR_SETTINGS = {
    "TITLE": "AgriGuard AI API",
    "VERSION": APP_VERSION,
    "SCHEMA_PATH_PREFIX": "/api/v1",
}
