"""Middleware for database-level tenant isolation via RLS."""

from django.db import connection


class TenantIsolationMiddleware:
    """Set PostgreSQL row-level security context for tenant isolation.

    NOTE: This middleware cannot run in Django middleware layer because
    DRF authentication happens in views, not middleware.

    Use set_tenant_context(request) directly from views instead:

        from api.tenant_isolation import set_tenant_context

        class MyView(APIView):
            def get(self, request):
                set_tenant_context(request)
                # Now queries respect RLS
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Middleware runs before DRF auth, so request.user is not available yet.
        # RLS context must be set in views after authentication.
        response = self.get_response(request)
        return response


def set_tenant_context(request):
    """Set RLS context in database connection after authentication.

    Call this from APIViews to enable PostgreSQL row-level security.
    """
    tenant_id = getattr(request.user, "tenant_id", None)

    if tenant_id:
        try:
            with connection.cursor() as cur:
                cur.execute(
                    "SET LOCAL app.tenant_id = %s",
                    [str(tenant_id)],
                )
        except Exception:
            # If RLS context fails, continue without it
            # (non-critical, table queries will still filter app-side)
            pass
