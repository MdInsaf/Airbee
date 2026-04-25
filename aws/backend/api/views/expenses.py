import uuid
from decimal import Decimal
from datetime import datetime
from django.db import connection
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status


EXPENSE_CATEGORIES = {
    "utilities", "salaries", "maintenance", "supplies", "food_beverage",
    "marketing", "laundry", "repairs", "insurance", "taxes", "rent", "other"
}


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


def _safe_float(v, d=0.0):
    try:
        return float(v)
    except Exception:
        return d


def _parse_date(raw):
    try:
        return datetime.strptime(str(raw), "%Y-%m-%d").date()
    except Exception:
        return None


class ExpenseList(APIView):
    def get(self, request):
        tenant_id = request.user.tenant_id
        params = [tenant_id]
        filters = ""
        if request.GET.get("from"):
            d = _parse_date(request.GET["from"])
            if d:
                filters += " AND e.expense_date >= %s"
                params.append(d)
        if request.GET.get("to"):
            d = _parse_date(request.GET["to"])
            if d:
                filters += " AND e.expense_date <= %s"
                params.append(d)
        if request.GET.get("category"):
            filters += " AND e.category = %s"
            params.append(request.GET["category"])

        try:
            with connection.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT e.id, e.tenant_id, e.category, e.description, e.amount,
                           e.expense_date, e.payment_method, e.notes, e.created_at, e.updated_at
                    FROM expenses e
                    WHERE e.tenant_id = %s{filters}
                    ORDER BY e.expense_date DESC, e.created_at DESC
                    """,
                    params,
                )
                cols = [c[0] for c in cur.description]
                rows = [_serialize(r, cols) for r in cur.fetchall()]
                # Also return summary
                cur.execute(
                    f"""
                    SELECT COALESCE(SUM(amount), 0), category
                    FROM expenses e
                    WHERE e.tenant_id = %s{filters}
                    GROUP BY category
                    """,
                    params,
                )
                summary = {row[1]: float(row[0]) for row in cur.fetchall()}
            return Response({"expenses": rows, "summary": summary, "total": sum(summary.values())})
        except Exception:
            return Response({"expenses": [], "summary": {}, "total": 0})

    def post(self, request):
        tenant_id = request.user.tenant_id
        d = request.data
        description = (d.get("description") or "").strip()
        category = str(d.get("category") or "other").strip()
        if category not in EXPENSE_CATEGORIES:
            category = "other"
        amount = _safe_float(d.get("amount"))
        if amount <= 0:
            return Response({"error": "Amount must be greater than 0"}, status=status.HTTP_400_BAD_REQUEST)
        if not description:
            return Response({"error": "Description is required"}, status=status.HTTP_400_BAD_REQUEST)

        expense_date = _parse_date(d.get("expense_date")) or datetime.today().date()
        exp_id = str(uuid.uuid4())
        try:
            with connection.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO expenses (id, tenant_id, category, description, amount,
                                         expense_date, payment_method, notes)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                    RETURNING id, tenant_id, category, description, amount,
                              expense_date, payment_method, notes, created_at
                    """,
                    [
                        exp_id, tenant_id, category, description, amount, expense_date,
                        str(d.get("payment_method") or "cash").strip(),
                        (d.get("notes") or "").strip() or None,
                    ],
                )
                cols = [c[0] for c in cur.description]
                row = _serialize(cur.fetchone(), cols)
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(row, status=status.HTTP_201_CREATED)


class ExpenseDetail(APIView):
    def put(self, request, expense_id):
        tenant_id = request.user.tenant_id
        d = request.data
        try:
            with connection.cursor() as cur:
                cur.execute(
                    """
                    UPDATE expenses SET
                        category = COALESCE(%s, category),
                        description = COALESCE(%s, description),
                        amount = COALESCE(%s, amount),
                        expense_date = COALESCE(%s, expense_date),
                        payment_method = COALESCE(%s, payment_method),
                        notes = COALESCE(%s, notes),
                        updated_at = NOW()
                    WHERE id = %s AND tenant_id = %s
                    RETURNING id
                    """,
                    [
                        d.get("category") or None,
                        d.get("description") or None,
                        _safe_float(d["amount"]) if "amount" in d else None,
                        _parse_date(d.get("expense_date")),
                        d.get("payment_method") or None,
                        d.get("notes") or None,
                        expense_id, tenant_id,
                    ],
                )
                if not cur.fetchone():
                    return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"success": True})

    def delete(self, request, expense_id):
        tenant_id = request.user.tenant_id
        with connection.cursor() as cur:
            cur.execute(
                "DELETE FROM expenses WHERE id = %s AND tenant_id = %s",
                [expense_id, tenant_id],
            )
        return Response(status=status.HTTP_204_NO_CONTENT)
