from django.conf import settings
from django.urls import path, include
from api.views.health import LiveHealthView, ReadyHealthView

urlpatterns = [
    path("health/live", LiveHealthView.as_view()),
    path("health/ready", ReadyHealthView.as_view()),
]

if settings.API_SURFACE in {"all", "platform"}:
    # API v1 only. Version detection and future v2 support via Accept-Version header.
    # Do NOT advertise v2 until genuine separate serializers/routes exist.
    urlpatterns.extend(
        [
            path("api/", include("api.urls")),
            path("api/v1/", include("api.urls")),
            path("ai/", include("api.urls_ai")),
            path("ai/v1/", include("api.urls_ai")),
        ]
    )

if settings.API_SURFACE in {"all", "public"}:
    urlpatterns.extend(
        [
            path("public/", include("api.urls_public")),
            path("public/v1/", include("api.urls_public")),
            path("public/v2/", include("api.urls_public")),
        ]
    )
