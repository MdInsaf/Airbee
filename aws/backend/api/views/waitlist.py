import uuid
from decimal import Decimal
from datetime import datetime
from django.db import connection
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny


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


def _parse_date(raw):
    try:
        return datetime.strptime(str(raw), "%Y-%m-%d").date()
    except Exception:
        return None


class WaitlistList(APIView):
    """GET /api/waitlist  (admin)"""

    def get(self, request):
        tenant_id = request.user.tenant_id
        try:
            with connection.cursor() as cur:
                cur.execute(
                    """
                    SELECT w.id, w.tenant_id, w.room_id, w.guest_name, w.guest_email,
                           w.guest_phone, w.check_in, w.check_out, w.guests, w.status,
                           w.notes, w.created_at,
                           r.name AS room_name
                    FROM waitlist w
                    LEFT JOIN rooms r ON r.id = w.room_id
                    WHERE w.tenant_id = %s AND w.status = 'waiting'
                    ORDER BY w.created_at ASC
                    """,
                    [tenant_id],
                )
                cols = [c[0] for c in cur.description]
                rows = [_serialize(r, cols) for r in cur.fetchall()]
            return Response(rows)
        except Exception:
            return Response([])


class WaitlistDetail(APIView):
    """PUT /api/waitlist/{id} — update status (notified/booked/expired)"""

    def put(self, request, waitlist_id):
        tenant_id = request.user.tenant_id
        new_status = str(request.data.get("status") or "").strip()
        allowed = {"waiting", "notified", "booked", "expired"}
        if new_status not in allowed:
            return Response({"error": "Invalid status"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            with connection.cursor() as cur:
                cur.execute(
                    "UPDATE waitlist SET status = %s, updated_at = NOW() WHERE id = %s AND tenant_id = %s",
                    [new_status, waitlist_id, tenant_id],
                )
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"success": True})

    def delete(self, request, waitlist_id):
        tenant_id = request.user.tenant_id
        with connection.cursor() as cur:
            cur.execute(
                "DELETE FROM waitlist WHERE id = %s AND tenant_id = %s",
                [waitlist_id, tenant_id],
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class PublicWaitlistCreate(APIView):
    """POST /public/waitlist  — guest submits from public booking page"""
    permission_classes = [AllowAny]

    def post(self, request):
        d = request.data
        tenant_id = d.get("tenant_id")
        room_id = d.get("room_id")
        guest_name = (d.get("guest_name") or "").strip()
        guest_email = (d.get("guest_email") or "").strip()
        check_in = _parse_date(d.get("check_in"))
        check_out = _parse_date(d.get("check_out"))

        if not all([tenant_id, room_id, guest_name, guest_email, check_in, check_out]):
            return Response({"error": "All fields required"}, status=status.HTTP_400_BAD_REQUEST)

        waitlist_id = str(uuid.uuid4())
        try:
            with connection.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO waitlist (id, tenant_id, room_id, guest_name, guest_email,
                                          guest_phone, check_in, check_out, guests, notes)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    RETURNING id, guest_name, check_in, check_out
                    """,
                    [
                        waitlist_id, tenant_id, room_id,
                        guest_name, guest_email,
                        (d.get("guest_phone") or "").strip() or None,
                        check_in, check_out,
                        max(1, int(d.get("guests") or 1)),
                        (d.get("notes") or "").strip() or None,
                    ],
                )
                cols = [c[0] for c in cur.description]
                row = _serialize(cur.fetchone(), cols)
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"message": "Added to waitlist", "id": row["id"]}, status=status.HTTP_201_CREATED)
