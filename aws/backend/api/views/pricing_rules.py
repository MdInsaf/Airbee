import uuid
from decimal import Decimal
from datetime import datetime
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


def _parse_date(raw):
    try:
        return datetime.strptime(str(raw), "%Y-%m-%d").date()
    except Exception:
        return None


def _safe_float(v, d=0.0):
    try:
        return float(v)
    except Exception:
        return d


class PricingRuleList(APIView):
    """GET /api/pricing-rules  POST /api/pricing-rules"""

    def get(self, request):
        tenant_id = request.user.tenant_id
        room_id = request.GET.get("room_id")
        params = [tenant_id]
        extra = ""
        if room_id:
            extra = " AND pr.room_id = %s"
            params.append(room_id)
        with connection.cursor() as cur:
            cur.execute(
                f"""
                SELECT pr.id, pr.room_id, pr.name, pr.rule_type, pr.adjustment_type,
                       pr.adjustment_value, pr.start_date, pr.end_date, pr.days_of_week,
                       pr.min_nights, pr.priority, pr.is_active, pr.created_at,
                       r.name AS room_name
                FROM room_pricing_rules pr
                LEFT JOIN rooms r ON r.id = pr.room_id
                WHERE pr.tenant_id = %s{extra}
                ORDER BY pr.priority ASC, pr.start_date ASC NULLS LAST
                """,
                params,
            )
            cols = [c[0] for c in cur.description]
            rows = [_serialize(r, cols) for r in cur.fetchall()]
        return Response(rows)

    def post(self, request):
        tenant_id = request.user.tenant_id
        d = request.data
        name = (d.get("name") or "").strip()
        if not name:
            return Response({"error": "Rule name is required"}, status=status.HTTP_400_BAD_REQUEST)

        rule_id = str(uuid.uuid4())
        room_id = d.get("room_id") or None
        rule_type = str(d.get("rule_type") or "seasonal").strip()
        adjustment_type = str(d.get("adjustment_type") or "percentage").strip()
        adjustment_value = _safe_float(d.get("adjustment_value"), 0.0)
        start_date = _parse_date(d.get("start_date"))
        end_date = _parse_date(d.get("end_date"))
        min_nights = int(d.get("min_nights") or 1)
        priority = int(d.get("priority") or 1)
        is_active = bool(d.get("is_active", True))
        days_of_week = d.get("days_of_week") or None  # e.g. [0,5,6] for Mon,Sat,Sun

        try:
            with connection.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO room_pricing_rules (
                        id, tenant_id, room_id, name, rule_type, adjustment_type,
                        adjustment_value, start_date, end_date, days_of_week,
                        min_nights, priority, is_active
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    RETURNING id, name, rule_type, adjustment_type, adjustment_value,
                              start_date, end_date, is_active, priority
                    """,
                    [
                        rule_id, tenant_id, room_id, name, rule_type, adjustment_type,
                        adjustment_value, start_date, end_date, days_of_week,
                        min_nights, priority, is_active,
                    ],
                )
                cols = [c[0] for c in cur.description]
                row = _serialize(cur.fetchone(), cols)
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(row, status=status.HTTP_201_CREATED)


class PricingRuleDetail(APIView):
    """PUT /api/pricing-rules/{id}  DELETE /api/pricing-rules/{id}"""

    def put(self, request, rule_id):
        tenant_id = request.user.tenant_id
        d = request.data
        try:
            with connection.cursor() as cur:
                cur.execute(
                    """
                    UPDATE room_pricing_rules SET
                        name = COALESCE(%s, name),
                        rule_type = COALESCE(%s, rule_type),
                        adjustment_type = COALESCE(%s, adjustment_type),
                        adjustment_value = COALESCE(%s, adjustment_value),
                        start_date = COALESCE(%s, start_date),
                        end_date = COALESCE(%s, end_date),
                        min_nights = COALESCE(%s, min_nights),
                        priority = COALESCE(%s, priority),
                        is_active = COALESCE(%s, is_active),
                        updated_at = NOW()
                    WHERE id = %s AND tenant_id = %s
                    RETURNING id
                    """,
                    [
                        d.get("name") or None,
                        d.get("rule_type") or None,
                        d.get("adjustment_type") or None,
                        _safe_float(d["adjustment_value"]) if "adjustment_value" in d else None,
                        _parse_date(d.get("start_date")),
                        _parse_date(d.get("end_date")),
                        int(d["min_nights"]) if "min_nights" in d else None,
                        int(d["priority"]) if "priority" in d else None,
                        bool(d["is_active"]) if "is_active" in d else None,
                        rule_id, tenant_id,
                    ],
                )
                if not cur.fetchone():
                    return Response({"error": "Rule not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"success": True})

    def delete(self, request, rule_id):
        tenant_id = request.user.tenant_id
        with connection.cursor() as cur:
            cur.execute(
                "DELETE FROM room_pricing_rules WHERE id = %s AND tenant_id = %s",
                [rule_id, tenant_id],
            )
        return Response(status=status.HTTP_204_NO_CONTENT)
