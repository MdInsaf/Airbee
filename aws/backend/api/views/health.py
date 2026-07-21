"""Unauthenticated liveness and dependency-readiness probes."""

from django.db import connection
from rest_framework.response import Response
from rest_framework.views import APIView


def database_is_ready() -> bool:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return True
    except Exception:
        return False


class LiveHealthView(APIView):
    authentication_classes = []
    permission_classes = []
    throttle_classes = []

    def get(self, request):
        return Response({"status": "ok", "service": "airbee-api"})


class ReadyHealthView(APIView):
    authentication_classes = []
    permission_classes = []
    throttle_classes = []

    def get(self, request):
        if not database_is_ready():
            return Response(
                {
                    "status": "unavailable",
                    "checks": {"database": "failed"},
                },
                status=503,
            )
        return Response(
            {
                "status": "ok",
                "checks": {"database": "ok"},
            }
        )
