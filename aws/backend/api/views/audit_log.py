import uuid
from decimal import Decimal
from django.db import connection
from rest_framework.views import APIView
from rest_framework.response import Response


def _serialize(row, columns):
    obj = dict(zip(columns, row))
    for k, v in obj.items():
        if isinstance(v, uuid.UUID):
            obj[k] = str(v)
        elif isinstance(v, Decimal):
            obj[k] = float(v)
        elif hasattr(v, "isoformat"):
            obj[k] = v.isoformat()
    return obj


class AuditLogList(APIView):
    """GET /api/audit-logs?entity_type=bookings&limit=50"""

    def get(self, request):
        tenant_id = request.user.tenant_id
        entity_type = request.GET.get("entity_type")
        limit = min(int(request.GET.get("limit") or 100), 200)
        params = [tenant_id]
        extra = ""
        if entity_type:
            extra = " AND entity_type = %s"
            params.append(entity_type)
        params.append(limit)
        try:
            with connection.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id, tenant_id, user_id, action, entity_type, entity_id,
                           old_value, new_value, ip_address, created_at
                    FROM audit_logs
                    WHERE tenant_id = %s{extra}
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    params,
                )
                cols = [c[0] for c in cur.description]
                rows = [_serialize(r, cols) for r in cur.fetchall()]
            return Response(rows)
        except Exception:
            return Response([])


def log_action(tenant_id, action, entity_type, entity_id=None, old_value=None, new_value=None, request=None):
    """Utility to write an audit log entry."""
    import json
    user_id = None
    ip_address = None
    if request:
        try:
            user_id = str(request.user.id) if hasattr(request.user, "id") else None
        except Exception:
            pass
        try:
            ip_address = (
                request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
                or request.META.get("REMOTE_ADDR")
            )
        except Exception:
            pass
    try:
        with connection.cursor() as cur:
            cur.execute(
                """
                INSERT INTO audit_logs (id, tenant_id, user_id, action, entity_type, entity_id,
                                        old_value, new_value, ip_address)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                [
                    str(uuid.uuid4()), tenant_id, user_id, action, entity_type,
                    str(entity_id) if entity_id else None,
                    json.dumps(old_value) if old_value is not None else None,
                    json.dumps(new_value) if new_value is not None else None,
                    ip_address,
                ],
            )
    except Exception:
        pass
