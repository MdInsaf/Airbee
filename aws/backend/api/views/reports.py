import csv
import io
from datetime import datetime, date
from decimal import Decimal
import uuid

from django.db import connection, transaction
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.http import HttpResponse


def _safe_float(v, d=0.0):
    try:
        return float(v)
    except Exception:
        return d


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


def _parse_month(raw):
    try:
        return datetime.strptime(str(raw), "%Y-%m").date().replace(day=1)
    except Exception:
        today = timezone.now().date()
        return today.replace(day=1)


def _parse_date(raw):
    try:
        return datetime.strptime(str(raw), "%Y-%m-%d").date()
    except Exception:
        return None


class ReportsSummary(APIView):
    """GET /api/reports/summary?month=YYYY-MM"""

    def get(self, request):
        tenant_id = request.user.tenant_id
        month_start = _parse_month(request.GET.get("month"))
        # End of month
        if month_start.month == 12:
            month_end = month_start.replace(year=month_start.year + 1, month=1)
        else:
            month_end = month_start.replace(month=month_start.month + 1)

        with connection.cursor() as cur:
            # Total rooms
            cur.execute("SELECT COUNT(*) FROM rooms WHERE tenant_id = %s", [tenant_id])
            total_rooms = int((cur.fetchone() or [0])[0] or 0)

            # Booking stats for the month
            cur.execute(
                """
                SELECT
                    COUNT(*) FILTER (WHERE status != 'cancelled') AS total_bookings,
                    COALESCE(SUM(total_amount) FILTER (WHERE status != 'cancelled'), 0) AS total_revenue,
                    COALESCE(SUM(base_amount) FILTER (WHERE status != 'cancelled'), 0) AS base_revenue,
                    COALESCE(SUM(tax_amount) FILTER (WHERE status != 'cancelled'), 0) AS total_gst,
                    COALESCE(SUM(service_charge) FILTER (WHERE status != 'cancelled'), 0) AS total_service_charge,
                    COALESCE(SUM(amount_paid) FILTER (WHERE status != 'cancelled'), 0) AS amount_collected,
                    COALESCE(SUM(GREATEST(total_amount - COALESCE(amount_paid, 0), 0)) FILTER (WHERE status != 'cancelled' AND payment_status != 'paid'), 0) AS outstanding,
                    COALESCE(SUM((check_out - check_in)) FILTER (WHERE status != 'cancelled'), 0) AS total_room_nights,
                    COUNT(*) FILTER (WHERE status = 'cancelled') AS cancellations
                FROM bookings
                WHERE tenant_id = %s
                  AND check_in >= %s AND check_in < %s
                """,
                [tenant_id, month_start, month_end],
            )
            row = cur.fetchone() or (0,) * 9
            total_bookings = int(row[0] or 0)
            total_revenue = _safe_float(row[1])
            base_revenue = _safe_float(row[2])
            total_gst = _safe_float(row[3])
            total_service = _safe_float(row[4])
            amount_collected = _safe_float(row[5])
            outstanding = _safe_float(row[6])
            total_room_nights = int(row[7] or 0)
            cancellations = int(row[8] or 0)

            # Days in month
            days_in_month = (month_end - month_start).days
            total_available_nights = total_rooms * days_in_month

            occupancy_rate = round((total_room_nights / total_available_nights) * 100, 1) if total_available_nights else 0
            adr = round(total_revenue / total_room_nights, 2) if total_room_nights else 0
            rev_par = round(total_revenue / total_available_nights, 2) if total_available_nights else 0

            # Revenue by source
            cur.execute(
                """
                SELECT COALESCE(booking_source, 'direct') AS source,
                       COUNT(*), COALESCE(SUM(total_amount), 0)
                FROM bookings
                WHERE tenant_id = %s AND status != 'cancelled'
                  AND check_in >= %s AND check_in < %s
                GROUP BY 1
                """,
                [tenant_id, month_start, month_end],
            )
            source_rows = cur.fetchall()
            revenue_by_source = [
                {"source": r[0], "bookings": int(r[1]), "revenue": _safe_float(r[2])}
                for r in source_rows
            ]

            # Expense total for month (if table exists)
            expense_total = 0.0
            try:
                cur.execute(
                    """
                    SELECT COALESCE(SUM(amount), 0)
                    FROM expenses
                    WHERE tenant_id = %s
                      AND expense_date >= %s AND expense_date < %s
                    """,
                    [tenant_id, month_start, month_end],
                )
                expense_total = _safe_float((cur.fetchone() or [0])[0])
            except Exception:
                pass

            # Daily revenue breakdown
            cur.execute(
                """
                SELECT
                    check_in AS day,
                    COALESCE(SUM(total_amount), 0) AS revenue,
                    COUNT(*) AS bookings
                FROM bookings
                WHERE tenant_id = %s AND status != 'cancelled'
                  AND check_in >= %s AND check_in < %s
                GROUP BY 1
                ORDER BY 1
                """,
                [tenant_id, month_start, month_end],
            )
            daily_rows = cur.fetchall()
            daily_revenue = [
                {"date": r[0].isoformat(), "revenue": _safe_float(r[1]), "bookings": int(r[2])}
                for r in daily_rows
            ]

            # Booking status breakdown
            cur.execute(
                """
                SELECT status, COUNT(*), COALESCE(SUM(total_amount), 0)
                FROM bookings
                WHERE tenant_id = %s AND check_in >= %s AND check_in < %s
                GROUP BY status
                """,
                [tenant_id, month_start, month_end],
            )
            status_breakdown = [
                {"status": r[0], "count": int(r[1]), "amount": _safe_float(r[2])}
                for r in cur.fetchall()
            ]

        net_revenue = round(total_revenue - expense_total, 2)

        return Response({
            "month": month_start.strftime("%Y-%m"),
            "kpis": {
                "total_bookings": total_bookings,
                "cancellations": cancellations,
                "total_room_nights": total_room_nights,
                "total_available_nights": total_available_nights,
                "occupancy_rate": occupancy_rate,
                "adr": adr,
                "rev_par": rev_par,
                "total_revenue": round(total_revenue, 2),
                "base_revenue": round(base_revenue, 2),
                "total_gst": round(total_gst, 2),
                "total_service_charge": round(total_service, 2),
                "amount_collected": round(amount_collected, 2),
                "outstanding": round(outstanding, 2),
                "expense_total": round(expense_total, 2),
                "net_revenue": net_revenue,
            },
            "revenue_by_source": revenue_by_source,
            "daily_revenue": daily_revenue,
            "status_breakdown": status_breakdown,
        })


class NightAuditReport(APIView):
    """GET /api/reports/night-audit?date=YYYY-MM-DD

    End-of-day snapshot used to close out the business day:
    arrivals, departures, in-house guests, room status mix,
    revenue posted, payments collected, and outstanding balances.
    """

    def get(self, request):
        tenant_id = request.user.tenant_id
        audit_date = _parse_date(request.GET.get("date")) or timezone.now().date()

        with connection.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM rooms WHERE tenant_id = %s", [tenant_id])
            total_rooms = int((cur.fetchone() or [0])[0] or 0)

            cur.execute(
                """
                SELECT status, COUNT(*)
                FROM rooms
                WHERE tenant_id = %s
                GROUP BY status
                """,
                [tenant_id],
            )
            room_status_mix = {r[0]: int(r[1]) for r in cur.fetchall()}

            cur.execute(
                """
                SELECT housekeeping_status, COUNT(*)
                FROM rooms
                WHERE tenant_id = %s
                GROUP BY housekeeping_status
                """,
                [tenant_id],
            )
            housekeeping_mix = {r[0]: int(r[1]) for r in cur.fetchall()}

            booking_select = """
                SELECT b.id, b.guest_name, b.guest_email, b.guest_phone,
                       b.check_in, b.check_out, b.guests,
                       b.total_amount, b.amount_paid,
                       b.status, b.payment_status,
                       r.name AS room_name
                FROM bookings b
                LEFT JOIN rooms r ON r.id = b.room_id
                WHERE b.tenant_id = %s
            """

            cur.execute(
                booking_select + " AND b.check_in = %s AND b.status != 'cancelled' ORDER BY r.name",
                [tenant_id, audit_date],
            )
            cols = [c[0] for c in cur.description]
            arrivals = [_serialize(r, cols) for r in cur.fetchall()]

            cur.execute(
                booking_select + " AND b.check_out = %s AND b.status != 'cancelled' ORDER BY r.name",
                [tenant_id, audit_date],
            )
            cols = [c[0] for c in cur.description]
            departures = [_serialize(r, cols) for r in cur.fetchall()]

            cur.execute(
                booking_select
                + " AND b.check_in <= %s AND b.check_out > %s AND b.status = 'confirmed' ORDER BY r.name",
                [tenant_id, audit_date, audit_date],
            )
            cols = [c[0] for c in cur.description]
            in_house = [_serialize(r, cols) for r in cur.fetchall()]

            cur.execute(
                """
                SELECT
                    COALESCE(SUM(total_amount), 0) AS revenue_posted,
                    COALESCE(SUM(base_amount), 0) AS base_posted,
                    COALESCE(SUM(tax_amount), 0) AS tax_posted,
                    COALESCE(SUM(service_charge), 0) AS service_posted,
                    COUNT(*) AS posting_count
                FROM bookings
                WHERE tenant_id = %s
                  AND status != 'cancelled'
                  AND check_in = %s
                """,
                [tenant_id, audit_date],
            )
            row = cur.fetchone() or (0, 0, 0, 0, 0)
            revenue_posted = _safe_float(row[0])
            base_posted = _safe_float(row[1])
            tax_posted = _safe_float(row[2])
            service_posted = _safe_float(row[3])
            posting_count = int(row[4] or 0)

            payments_collected = 0.0
            payment_count = 0
            try:
                with transaction.atomic():
                    cur.execute(
                        """
                        SELECT COALESCE(SUM(amount), 0), COUNT(*)
                        FROM booking_payments
                        WHERE tenant_id = %s
                          AND DATE(received_at) = %s
                        """,
                        [tenant_id, audit_date],
                    )
                    pay_row = cur.fetchone() or (0, 0)
                    payments_collected = _safe_float(pay_row[0])
                    payment_count = int(pay_row[1] or 0)
            except Exception:
                pass

            outstanding = sum(
                max(0.0, _safe_float(b.get("total_amount")) - _safe_float(b.get("amount_paid")))
                for b in in_house
                if b.get("payment_status") != "paid"
            )

        in_house_count = len(in_house)
        occupancy_rate = round((in_house_count / total_rooms) * 100, 1) if total_rooms else 0.0

        return Response({
            "date": audit_date.isoformat(),
            "totals": {
                "total_rooms": total_rooms,
                "in_house": in_house_count,
                "arrivals": len(arrivals),
                "departures": len(departures),
                "occupancy_rate": occupancy_rate,
                "revenue_posted": round(revenue_posted, 2),
                "base_posted": round(base_posted, 2),
                "tax_posted": round(tax_posted, 2),
                "service_posted": round(service_posted, 2),
                "posting_count": posting_count,
                "payments_collected": round(payments_collected, 2),
                "payment_count": payment_count,
                "outstanding": round(outstanding, 2),
            },
            "room_status_mix": room_status_mix,
            "housekeeping_mix": housekeeping_mix,
            "arrivals": arrivals,
            "departures": departures,
            "in_house": in_house,
        })


class GSTReport(APIView):
    """GET /api/reports/gst?month=YYYY-MM"""

    def get(self, request):
        tenant_id = request.user.tenant_id
        month_start = _parse_month(request.GET.get("month"))
        if month_start.month == 12:
            month_end = month_start.replace(year=month_start.year + 1, month=1)
        else:
            month_end = month_start.replace(month=month_start.month + 1)

        with connection.cursor() as cur:
            cur.execute(
                """
                SELECT
                    b.id, b.guest_name, b.guest_email, b.guest_phone,
                    b.check_in, b.check_out,
                    b.base_amount, b.tax_amount, b.service_charge, b.total_amount,
                    b.payment_status, b.status,
                    r.name AS room_name,
                    t.gst_percentage, t.gst_enabled, t.name AS property_name
                FROM bookings b
                JOIN tenants t ON t.id = b.tenant_id
                LEFT JOIN rooms r ON r.id = b.room_id
                WHERE b.tenant_id = %s
                  AND b.status != 'cancelled'
                  AND b.check_in >= %s AND b.check_in < %s
                ORDER BY b.check_in ASC
                """,
                [tenant_id, month_start, month_end],
            )
            cols = [c[0] for c in cur.description]
            rows = [_serialize(r, cols) for r in cur.fetchall()]

            # Totals
            cur.execute(
                """
                SELECT
                    COALESCE(SUM(base_amount), 0),
                    COALESCE(SUM(tax_amount), 0),
                    COALESCE(SUM(service_charge), 0),
                    COALESCE(SUM(total_amount), 0)
                FROM bookings
                WHERE tenant_id = %s AND status != 'cancelled'
                  AND check_in >= %s AND check_in < %s
                """,
                [tenant_id, month_start, month_end],
            )
            totals = cur.fetchone() or (0, 0, 0, 0)

        return Response({
            "month": month_start.strftime("%Y-%m"),
            "bookings": rows,
            "totals": {
                "base_amount": _safe_float(totals[0]),
                "tax_amount": _safe_float(totals[1]),
                "service_charge": _safe_float(totals[2]),
                "total_amount": _safe_float(totals[3]),
            },
        })


class ExportBookings(APIView):
    """GET /api/reports/export/bookings?from=YYYY-MM-DD&to=YYYY-MM-DD"""

    def get(self, request):
        tenant_id = request.user.tenant_id
        from_date = _parse_date(request.GET.get("from"))
        to_date = _parse_date(request.GET.get("to"))

        params = [tenant_id]
        filters = ""
        if from_date:
            filters += " AND b.check_in >= %s"
            params.append(from_date)
        if to_date:
            filters += " AND b.check_in <= %s"
            params.append(to_date)

        with connection.cursor() as cur:
            cur.execute(
                f"""
                SELECT b.id, b.guest_name, b.guest_email, b.guest_phone,
                       b.check_in, b.check_out, b.guests, b.status, b.payment_status,
                       b.total_amount, b.base_amount, b.tax_amount, b.service_charge,
                       b.amount_paid, b.payment_method,
                       COALESCE(b.booking_source, 'direct') AS booking_source,
                       b.notes, b.created_at,
                       r.name AS room_name
                FROM bookings b
                LEFT JOIN rooms r ON r.id = b.room_id
                WHERE b.tenant_id = %s{filters}
                ORDER BY b.check_in DESC
                """,
                params,
            )
            cols = [c[0] for c in cur.description]
            rows = cur.fetchall()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(cols)
        for row in rows:
            writer.writerow([
                v.isoformat() if hasattr(v, "isoformat") else
                str(v) if isinstance(v, uuid.UUID) else
                float(v) if isinstance(v, Decimal) else v
                for v in row
            ])

        response = HttpResponse(output.getvalue(), content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="bookings_export.csv"'
        return response


class ExportGuests(APIView):
    """GET /api/reports/export/guests"""

    def get(self, request):
        tenant_id = request.user.tenant_id

        with connection.cursor() as cur:
            cur.execute(
                """
                SELECT g.name, g.email, g.phone, g.is_vip,
                       ARRAY_TO_STRING(g.tags, ', ') AS tags,
                       g.notes,
                       COUNT(b.id) AS total_bookings,
                       COALESCE(SUM(b.total_amount) FILTER (WHERE b.status != 'cancelled'), 0) AS lifetime_value,
                       MAX(b.check_in) AS last_stay,
                       g.created_at
                FROM guest_profiles g
                LEFT JOIN bookings b ON b.guest_email = g.email AND b.tenant_id = g.tenant_id
                WHERE g.tenant_id = %s
                GROUP BY g.id, g.name, g.email, g.phone, g.is_vip, g.tags, g.notes, g.created_at
                ORDER BY lifetime_value DESC
                """,
                [tenant_id],
            )
            cols = [c[0] for c in cur.description]
            rows = cur.fetchall()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(cols)
        for row in rows:
            writer.writerow([
                v.isoformat() if hasattr(v, "isoformat") else
                str(v) if isinstance(v, uuid.UUID) else
                float(v) if isinstance(v, Decimal) else v
                for v in row
            ])

        response = HttpResponse(output.getvalue(), content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="guests_export.csv"'
        return response


class ExportExpenses(APIView):
    """GET /api/reports/export/expenses?from=YYYY-MM-DD&to=YYYY-MM-DD"""

    def get(self, request):
        tenant_id = request.user.tenant_id
        from_date = _parse_date(request.GET.get("from"))
        to_date = _parse_date(request.GET.get("to"))

        params = [tenant_id]
        filters = ""
        if from_date:
            filters += " AND expense_date >= %s"
            params.append(from_date)
        if to_date:
            filters += " AND expense_date <= %s"
            params.append(to_date)

        with connection.cursor() as cur:
            cur.execute(
                f"""
                SELECT expense_date, category, description, amount,
                       payment_method, notes, created_at
                FROM expenses
                WHERE tenant_id = %s{filters}
                ORDER BY expense_date DESC
                """,
                params,
            )
            cols = [c[0] for c in cur.description]
            rows = cur.fetchall()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(cols)
        for row in rows:
            writer.writerow([
                v.isoformat() if hasattr(v, "isoformat") else
                str(v) if isinstance(v, uuid.UUID) else
                float(v) if isinstance(v, Decimal) else v
                for v in row
            ])

        response = HttpResponse(output.getvalue(), content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="expenses_export.csv"'
        return response


class ExportGSTCsv(APIView):
    """GET /api/reports/export/gst?month=YYYY-MM"""

    def get(self, request):
        tenant_id = request.user.tenant_id
        month_start = _parse_month(request.GET.get("month"))
        if month_start.month == 12:
            month_end = month_start.replace(year=month_start.year + 1, month=1)
        else:
            month_end = month_start.replace(month=month_start.month + 1)

        with connection.cursor() as cur:
            cur.execute(
                """
                SELECT b.guest_name, b.guest_email, b.guest_phone,
                       r.name AS room_name,
                       b.check_in, b.check_out,
                       b.base_amount, b.tax_amount, b.service_charge, b.total_amount,
                       t.gst_percentage, b.payment_status, b.status
                FROM bookings b
                JOIN tenants t ON t.id = b.tenant_id
                LEFT JOIN rooms r ON r.id = b.room_id
                WHERE b.tenant_id = %s
                  AND b.status != 'cancelled'
                  AND b.check_in >= %s AND b.check_in < %s
                ORDER BY b.check_in ASC
                """,
                [tenant_id, month_start, month_end],
            )
            cols = [c[0] for c in cur.description]
            rows = cur.fetchall()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(cols)
        for row in rows:
            writer.writerow([
                v.isoformat() if hasattr(v, "isoformat") else
                str(v) if isinstance(v, uuid.UUID) else
                float(v) if isinstance(v, Decimal) else v
                for v in row
            ])

        response = HttpResponse(output.getvalue(), content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="gst_report_{month_start.strftime("%Y-%m")}.csv"'
        return response
