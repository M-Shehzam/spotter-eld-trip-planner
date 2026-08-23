"""
Django settings for the Spotter ELD trip planner.

Configuration is environment driven so the same code runs locally and on
Render. Two fallbacks keep a fresh clone runnable with no infrastructure:

    DATABASE_URL unset  -> SQLite file in the project root
    no cache backend    -> in-process LocMemCache

No API keys are required. Place resolution runs against the gazetteer
committed in ``data/us_places.csv`` and routing uses the OSRM demo server.
"""

import os
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


def env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


# --------------------------------------------------------------------------
# Core
# --------------------------------------------------------------------------

SECRET_KEY = os.getenv("SECRET_KEY", "dev-insecure-key-do-not-use-in-production")
DEBUG = env_bool("DEBUG", True)
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "*")

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "apps.planner",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": []},
    }
]

# --------------------------------------------------------------------------
# Database
# --------------------------------------------------------------------------

DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=env_int("DB_CONN_MAX_AGE", 600),
        conn_health_checks=True,
    )
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --------------------------------------------------------------------------
# Cache
# --------------------------------------------------------------------------

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "eld-planner",
        "TIMEOUT": env_int("CACHE_TTL_SECONDS", 60 * 60 * 6),
        "OPTIONS": {"MAX_ENTRIES": 500},
    }
}

# --------------------------------------------------------------------------
# Static files
# --------------------------------------------------------------------------

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}

# --------------------------------------------------------------------------
# Internationalisation
# --------------------------------------------------------------------------

LANGUAGE_CODE = "en-us"
TIME_ZONE = os.getenv("TIME_ZONE", "America/Chicago")
USE_I18N = False
USE_TZ = True

# --------------------------------------------------------------------------
# CORS
# --------------------------------------------------------------------------

CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS")
CORS_ALLOW_ALL_ORIGINS = env_bool("CORS_ALLOW_ALL_ORIGINS", not CORS_ALLOWED_ORIGINS)
CORS_ALLOWED_ORIGIN_REGEXES = env_list("CORS_ALLOWED_ORIGIN_REGEXES")

CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")

# --------------------------------------------------------------------------
# Django REST framework
# --------------------------------------------------------------------------

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "UNAUTHENTICATED_USER": None,
    "EXCEPTION_HANDLER": "apps.planner.errors.exception_handler",
}

# --------------------------------------------------------------------------
# Domain configuration
# --------------------------------------------------------------------------

# Gazetteer of US places used for both resolving typed locations and naming
# the stops the planner inserts along the route.
PLACES_CSV = Path(os.getenv("PLACES_CSV", BASE_DIR / "data" / "us_places.csv"))

# Routing. OSRM's demo server needs no key, which is why it is the default.
OSRM_BASE_URL = os.getenv("OSRM_BASE_URL", "https://router.project-osrm.org")
OSRM_FALLBACK_URL = os.getenv("OSRM_FALLBACK_URL", "")
ROUTING_TIMEOUT_SECONDS = env_float("ROUTING_TIMEOUT_SECONDS", 20.0)
ROUTING_RETRIES = env_int("ROUTING_RETRIES", 2)

# Scales the routing provider's duration into planned truck driving time.
# OSRM's demo profile already implies 48-58 mph over a long haul, which is
# the band a dispatcher plans a Class 8 truck at, so the default is 1.0.
TRUCK_SPEED_FACTOR = env_float("TRUCK_SPEED_FACTOR", 1.0)

# Hours of service, 49 CFR 395.3, property-carrying driver.
HOS_DRIVING_LIMIT_HOURS = env_float("HOS_DRIVING_LIMIT_HOURS", 11.0)
HOS_DUTY_WINDOW_HOURS = env_float("HOS_DUTY_WINDOW_HOURS", 14.0)
HOS_DRIVING_BEFORE_BREAK_HOURS = env_float("HOS_DRIVING_BEFORE_BREAK_HOURS", 8.0)
HOS_BREAK_HOURS = env_float("HOS_BREAK_HOURS", 0.5)
HOS_RESET_HOURS = env_float("HOS_RESET_HOURS", 10.0)
HOS_CYCLE_LIMIT_HOURS = env_float("HOS_CYCLE_LIMIT_HOURS", 70.0)
HOS_CYCLE_DAYS = env_int("HOS_CYCLE_DAYS", 8)
HOS_RESTART_HOURS = env_float("HOS_RESTART_HOURS", 34.0)

# Trip assumptions stated in the brief.
PICKUP_HOURS = env_float("PICKUP_HOURS", 1.0)
DROPOFF_HOURS = env_float("DROPOFF_HOURS", 1.0)
FUEL_INTERVAL_MILES = env_float("FUEL_INTERVAL_MILES", 1000.0)
FUEL_STOP_HOURS = env_float("FUEL_STOP_HOURS", 0.5)

# --------------------------------------------------------------------------
# Logging
# --------------------------------------------------------------------------

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {"format": "%(asctime)s %(levelname)-7s %(name)s | %(message)s"}
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "standard"}
    },
    "root": {"handlers": ["console"], "level": os.getenv("LOG_LEVEL", "INFO")},
    "loggers": {
        "django.request": {"handlers": ["console"], "level": "ERROR", "propagate": False}
    },
}

# --------------------------------------------------------------------------
# Production hardening
# --------------------------------------------------------------------------

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True)
    SECURE_HSTS_SECONDS = env_int("SECURE_HSTS_SECONDS", 60 * 60 * 24 * 30)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
