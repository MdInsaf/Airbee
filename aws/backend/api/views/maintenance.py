import uuid
from decimal import Decimal
from django.db import connection
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status


ALLOWED_PRIORITY = {"low", "normal", "high", "urgent"}
ALLOWED_STATUS = {"open", "in_progress", "resolved", "closed"}


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


class MaintenanceList(APIView):
    def get(self, request):
        tenant_id = request.user.tenant_id
        req_status = request.GET.get("status")
        params = [tenant_id]
        extra = ""
        if req_status:
            extra = " AND m.status = %s"
            params.append(req_status)
        try:
            with connection.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT m.id, m.tenant_id, m.room_id, m.title, m.description,
                           m.priority, m.status, m.reported_by, m.resolved_at,
                           m.created_at, m.updated_at,
                           r.name AS room_name
                    FROM maintenance_requests m
                    LEFT JOIN rooms r ON r.id = m.room_id
                    WHERE m.tenant_id = %s{extra}
                    ORDER BY
                        CASE m.priority WHEN 'urgent' THEN 1 WHEN 'high' THEN 2 WHEN 'normal' THEN 3 ELSE 4 END,
                        m.created_at DESC
                    """,
                    params,
                )
                cols = [c[0] for c in cur.description]
                rows = [_serialize(r, cols) for r in cur.fetchall()]
            return Response(rows)
        except Exception:
            return Response([])

    def post(self, request):
        tenant_id = request.user.tenant_id
        d = request.data
        title = (d.get("title") or "").strip()
        if not title:
            return Response({"error": "Title is required"}, status=status.HTTP_400_BAD_REQUEST)

        priority = str(d.get("priority") or "normal").strip()
        if priority not in ALLOWED_PRIORITY:
            priority = "normal"

        req_id = str(uuid.uuid4())
        try:
            with connection.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO maintenance_requests
                        (id, tenant_id, room_id, title, description, priority, status, reported_by)
                    VALUES (%s,%s,%s,%s,%s,%s,'open',%s)
                    RETURNING id, tenant_id, room_id, title, description, priority, status,
                              reported_by, resolved_at, created_at, updated_at
                    """,
                    [
                        req_id, tenant_id,
                        d.get("room_id") or None,
                        title,
                        (d.get("description") or "").strip() or None,
                        priority,
                        (d.get("reported_by") or "").strip() or None,
                    ],
                )
                cols = [c[0] for c in cur.description]
                row = _serialize(cur.fetchone(), cols)
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(row, status=status.HTTP_201_CREATED)


class MaintenanceDetail(APIView):
    def put(self, request, req_id):
        tenant_id = request.user.tenant_id
        d = request.data
        new_status = d.get("status")
        if new_status and new_status not in ALLOWED_STATUS:
            return Response({"error": "Invalid status"}, status=status.HTTP_400_BAD_REQUEST)
        priority = d.get("priority")
        if priority and priority not in ALLOWED_PRIORITY:
            return Response({"error": "Invalid priority"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            with connection.cursor() as cur:
                cur.execute(
                    """
                    UPDATE maintenance_requests SET
                        title = COALESCE(%s, title),
                        description = COALESCE(%s, description),
                        priority = COALESCE(%s, priority),
                        status = COALESCE(%s, status),
                        reported_by = COALESCE(%s, reported_by),
                        resolved_at = CASE WHEN %s = 'resolved' THEN NOW() ELSE resolved_at END,
                        updated_at = NOW()
                    WHERE id = %s AND tenant_id = %s
                    RETURNING id
                    """,
                    [
                        d.get("title") or None,
                        d.get("description") or None,
                        priority,
                        new_status,
                        d.get("reported_by") or None,
                        new_status,
                        req_id, tenant_id,
                    ],
                )
                if not cur.fetchone():
                    return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"success": True})

    def delete(self, request, req_id):
        tenant_id = request.user.tenant_id
        with connection.cursor() as cur:
            cur.execute(
                "DELETE FROM maintenance_requests WHERE id = %s AND tenant_id = %s",
                [req_id, tenant_id],
            )
        return Response(status=status.HTTP_204_NO_CONTENT)
