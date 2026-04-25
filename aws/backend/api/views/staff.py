import uuid
from decimal import Decimal
from django.db import connection
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status


ALLOWED_ROLES = {"manager", "front_desk", "housekeeping", "maintenance", "staff"}


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


class StaffList(APIView):
    def get(self, request):
        tenant_id = request.user.tenant_id
        try:
            with connection.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, tenant_id, name, email, phone, role, department,
                           is_active, notes, created_at, updated_at
                    FROM staff_members
                    WHERE tenant_id = %s
                    ORDER BY name ASC
                    """,
                    [tenant_id],
                )
                cols = [c[0] for c in cur.description]
                rows = [_serialize(r, cols) for r in cur.fetchall()]
            return Response(rows)
        except Exception:
            return Response([])

    def post(self, request):
        tenant_id = request.user.tenant_id
        d = request.data
        name = (d.get("name") or "").strip()
        if not name:
            return Response({"error": "Name is required"}, status=status.HTTP_400_BAD_REQUEST)

        role = str(d.get("role") or "staff").strip()
        if role not in ALLOWED_ROLES:
            return Response({"error": "Invalid role"}, status=status.HTTP_400_BAD_REQUEST)

        staff_id = str(uuid.uuid4())
        try:
            with connection.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO staff_members (id, tenant_id, name, email, phone, role, department, is_active, notes)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,COALESCE(%s,true),%s)
                    RETURNING id, tenant_id, name, email, phone, role, department, is_active, notes, created_at
                    """,
                    [
                        staff_id, tenant_id, name,
                        d.get("email") or None,
                        d.get("phone") or None,
                        role,
                        (d.get("department") or "").strip() or None,
                        d.get("is_active", True),
                        (d.get("notes") or "").strip() or None,
                    ],
                )
                cols = [c[0] for c in cur.description]
                row = _serialize(cur.fetchone(), cols)
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(row, status=status.HTTP_201_CREATED)


class StaffDetail(APIView):
    def put(self, request, staff_id):
        tenant_id = request.user.tenant_id
        d = request.data
        role = d.get("role")
        if role and role not in ALLOWED_ROLES:
            return Response({"error": "Invalid role"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            with connection.cursor() as cur:
                cur.execute(
                    """
                    UPDATE staff_members SET
                        name = COALESCE(%s, name),
                        email = COALESCE(%s, email),
                        phone = COALESCE(%s, phone),
                        role = COALESCE(%s, role),
                        department = COALESCE(%s, department),
                        is_active = COALESCE(%s, is_active),
                        notes = COALESCE(%s, notes),
                        updated_at = NOW()
                    WHERE id = %s AND tenant_id = %s
                    RETURNING id
                    """,
                    [
                        d.get("name") or None,
                        d.get("email") or None,
                        d.get("phone") or None,
                        role,
                        d.get("department") or None,
                        d.get("is_active") if "is_active" in d else None,
                        d.get("notes") or None,
                        staff_id, tenant_id,
                    ],
                )
                if not cur.fetchone():
                    return Response({"error": "Staff member not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"success": True})

    def delete(self, request, staff_id):
        tenant_id = request.user.tenant_id
        with connection.cursor() as cur:
            cur.execute(
                "DELETE FROM staff_members WHERE id = %s AND tenant_id = %s",
                [staff_id, tenant_id],
            )
        return Response(status=status.HTTP_204_NO_CONTENT)
