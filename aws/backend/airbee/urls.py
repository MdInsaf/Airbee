from django.conf import settings
from django.urls import path, include
from api.views.health import LiveHealthView, ReadyHealthView

urlpatterns = [
    path("health/live", LiveHealthView.as_view()),
    path("health/ready", ReadyHealthView.as_view()),
]

if settings.API_SURFACE in {"all", "platform"}:
    # Support both versioned and non-versioned paths for backward compatibility
    # /api/bookings → uses Accept-Version header or defaults to v1
    # /api/v1/bookings → explicitly v1
    # /api/v2/bookings → explicitly v2
    urlpatterns.extend(
        [
            path("api/", include("api.urls")),
            path("api/v1/", include("api.urls")),
            path("api/v2/", include("api.urls")),
            path("ai/", include("api.urls_ai")),
            path("ai/v1/", include("api.urls_ai")),
            path("ai/v2/", include("api.urls_ai")),
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
