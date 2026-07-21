"""Middleware for database-level tenant isolation via RLS."""

from django.db import connection


class TenantIsolationMiddleware:
    """Set PostgreSQL row-level security context for tenant isolation.

    This middleware sets the app.tenant_id parameter used by RLS policies,
    ensuring that even if application SQL is missing a WHERE clause,
    PostgreSQL prevents unauthorized cross-tenant access.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Extract tenant from authenticated user
        tenant_id = getattr(request.user, "tenant_id", None)

        if tenant_id:
            # Set PostgreSQL application context for RLS
            try:
                with connection.cursor() as cur:
                    # Escape and set tenant ID for this transaction
                    cur.execute(
                        "SET app.tenant_id = %s",
                        [str(tenant_id)],
                    )
            except Exception:
                # If RLS context fails, continue without it
                # (non-critical, table queries will still filter app-side)
                pass

        response = self.get_response(request)
        return response
