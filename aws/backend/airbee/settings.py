import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

LOCAL_DEV = os.environ.get("LOCAL_DEV", "false").lower() == "true"

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "hackathon-airbee-secret-key-2025")
DEBUG = LOCAL_DEV
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "corsheaders",
    "rest_framework",
    "api",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
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
        "OPTIONS": {"sslmode": "require"},
        "CONN_MAX_AGE": 60,
    }
}

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["api.auth.CognitoAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "UNAUTHENTICATED_USER": None,
    "UNAUTHENTICATED_TOKEN": None,
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

CORS_ALLOW_HEADERS = ["authorization", "content-type"]

COGNITO_USER_POOL_ID = os.environ.get("COGNITO_USER_POOL_ID", "")
COGNITO_REGION = os.environ.get("AWS_REGION", "ap-south-1")
BEDROCK_REGION = os.environ.get("BEDROCK_REGION", "ap-south-1")

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True
