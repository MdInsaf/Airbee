from django.conf import settings
from django.urls import path, include

urlpatterns = []

if settings.API_SURFACE in {"all", "platform"}:
    urlpatterns.extend(
        [
            path("api/", include("api.urls")),
            path("ai/", include("api.urls_ai")),
        ]
    )

if settings.API_SURFACE in {"all", "public"}:
    urlpatterns.append(path("public/", include("api.urls_public")))
