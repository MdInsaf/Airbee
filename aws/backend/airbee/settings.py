import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

LOCAL_DEV = os.environ.get("LOCAL_DEV", "false").lower() == "true"

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if LOCAL_DEV:
        SECRET_KEY = "airbee-local-development-only"
    else:
        raise ImproperlyConfigured("DJANGO_SECRET_KEY must be configured")
DEBUG = LOCAL_DEV
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "corsheaders",
    "rest_framework",
    "api",
]

MIDDLEWARE = [
    "api.observability.RequestContextMiddleware",
    "api.versioning.APIVersionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    # TenantIsolationMiddleware must run in views (after DRF auth)
    # Not in middleware (which runs before). Set RLS context in each view.
]

ROOT_URLCONF = "airbee.urls"
ASGI_APPLICATION = "airbee.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "HOST": os.environ.get("DB_HOST", "localhost"),
        "PORT": os.environ.get("DB_PORT", "5432"),
        "NAME": os.environ.get("DB_NAME", "airbee"),
        "USER": os.environ.get("DB_USER", "airbee"),
        "PASSWORD": os.environ.get("DB_PASSWORD", "airbee123"),
        "OPTIONS": {"sslmode": os.environ.get("DB_SSLMODE", "require")},
        # Lambda should release connections after each request and rely on an
        # external pooler (RDS Proxy/Supabase pooler). Persistent per-container
        # Django connections multiply quickly during concurrency spikes.
        "CONN_MAX_AGE": int(
            os.environ.get("DB_CONN_MAX_AGE", "60" if LOCAL_DEV else "0")
        ),
        "CONN_HEALTH_CHECKS": True,
    }
}

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["api.auth.CognitoAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.ScopedRateThrottle"],
    "DEFAULT_THROTTLE_RATES": {
        "public_read": os.environ.get("THROTTLE_PUBLIC_READ", "60/minute"),
        "public_write": os.environ.get("THROTTLE_PUBLIC_WRITE", "10/minute"),
        "guest_access": os.environ.get("THROTTLE_GUEST_ACCESS", "10/minute"),
        "ical_export": os.environ.get("THROTTLE_ICAL_EXPORT", "30/minute"),
    },
    "NUM_PROXIES": int(os.environ.get("API_NUM_PROXIES", "1")),
    "UNAUTHENTICATED_USER": None,
    "UNAUTHENTICATED_TOKEN": None,
    "EXCEPTION_HANDLER": "api.exceptions.airbee_exception_handler",
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "airbee-api-throttles",
    }
}

API_SURFACE = os.environ.get("AIRBEE_API_SURFACE", "all").strip().lower()

# Platform surface: restrict CORS to known admin domains + local dev.
# Public/booking surface: allow all origins (serves guests on arbitrary custom domains).
if API_SURFACE == "platform":
    _platform_hosts = [h.strip() for h in os.environ.get("PLATFORM_HOSTS", "").split(",") if h.strip()]
    CORS_ALLOWED_ORIGINS = (
        [f"https://{h}" for h in _platform_hosts]
        + ["http://localhost:5173", "http://localhost:3000"]
    )
    CORS_ALLOW_ALL_ORIGINS = False
else:
    CORS_ALLOW_ALL_ORIGINS = True

CORS_ALLOW_HEADERS = [
    "authorization",
    "content-type",
    "idempotency-key",
    "x-request-id",
    "accept-version",
    "x-api-version",
]
CORS_EXPOSE_HEADERS = [
    "X-Request-ID",
    "Idempotency-Key",
    "Idempotency-Replayed",
    "API-Version",
    "API-Supported-Versions",
    "Deprecation",
    "Sunset",
]

COGNITO_USER_POOL_ID = os.environ.get("COGNITO_USER_POOL_ID", "")
COGNITO_CLIENT_ID = os.environ.get("COGNITO_CLIENT_ID", "")
COGNITO_REGION = os.environ.get("AWS_REGION", "ap-south-1")
BEDROCK_REGION = os.environ.get("BEDROCK_REGION", "ap-south-1")

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "api.observability.JsonFormatter",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": LOG_LEVEL,
    },
    "loggers": {
        "django.server": {
            "handlers": ["console"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True
