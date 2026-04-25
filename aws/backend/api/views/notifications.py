import uuid
from decimal import Decimal
from django.db import connection
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status


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


class NotificationList(APIView):
    """GET /api/notifications  POST /api/notifications/read-all"""

    def get(self, request):
        tenant_id = request.user.tenant_id
        try:
            with connection.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, tenant_id, type, title, message, is_read,
                           related_id, related_type, created_at
                    FROM notifications
                    WHERE tenant_id = %s
                    ORDER BY created_at DESC
                    LIMIT 50
                    """,
                    [tenant_id],
                )
                cols = [c[0] for c in cur.description]
                rows = [_serialize(r, cols) for r in cur.fetchall()]
                cur.execute(
                    "SELECT COUNT(*) FROM notifications WHERE tenant_id = %s AND is_read = false",
                    [tenant_id],
                )
                unread_count = int((cur.fetchone() or [0])[0] or 0)
            return Response({"notifications": rows, "unread_count": unread_count})
        except Exception:
            return Response({"notifications": [], "unread_count": 0})


class NotificationMarkRead(APIView):
    """PUT /api/notifications/{id}/read"""

    def put(self, request, notification_id):
        tenant_id = request.user.tenant_id
        try:
            with connection.cursor() as cur:
                if notification_id == "all":
                    cur.execute(
                        "UPDATE notifications SET is_read = true WHERE tenant_id = %s",
                        [tenant_id],
                    )
                else:
                    cur.execute(
                        "UPDATE notifications SET is_read = true WHERE id = %s AND tenant_id = %s",
                        [notification_id, tenant_id],
                    )
        except Exception:
            pass
        return Response({"success": True})


def create_notification(tenant_id, notif_type, title, message, related_id=None, related_type=None):
    """Utility to create a notification — call from booking/housekeeping/maintenance views."""
    try:
        with connection.cursor() as cur:
            cur.execute(
                """
                INSERT INTO notifications (id, tenant_id, type, title, message, related_id, related_type)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                [str(uuid.uuid4()), tenant_id, notif_type, title, message, related_id, related_type],
            )
    except Exception:
        pass
