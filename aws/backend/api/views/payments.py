import uuid
from decimal import Decimal
from datetime import datetime
from django.db import connection, transaction
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status


ALLOWED_PAYMENT_METHODS = {"cash", "card", "bank_transfer", "upi", "cheque", "other"}


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


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


def _parse_date(raw):
    try:
        return datetime.strptime(str(raw), "%Y-%m-%d").date()
    except Exception:
        return None


class BookingPaymentList(APIView):
    """GET /api/bookings/{id}/payments  POST /api/bookings/{id}/payments"""

    def get(self, request, booking_id):
        tenant_id = request.user.tenant_id
        with connection.cursor() as cur:
            cur.execute(
                """
                SELECT bp.id, bp.booking_id, bp.amount, bp.payment_method,
                       bp.payment_date, bp.notes, bp.created_at
                FROM booking_payments bp
                JOIN bookings b ON b.id = bp.booking_id
                WHERE bp.booking_id = %s AND b.tenant_id = %s
                ORDER BY bp.payment_date DESC, bp.created_at DESC
                """,
                [booking_id, tenant_id],
            )
            cols = [c[0] for c in cur.description]
            rows = [_serialize(r, cols) for r in cur.fetchall()]
        return Response(rows)

    def post(self, request, booking_id):
        tenant_id = request.user.tenant_id
        d = request.data
        amount = _safe_float(d.get("amount"))
        if amount <= 0:
            return Response({"error": "Amount must be greater than 0"}, status=status.HTTP_400_BAD_REQUEST)

        payment_method = str(d.get("payment_method") or "cash").strip()
        if payment_method not in ALLOWED_PAYMENT_METHODS:
            payment_method = "other"

        payment_date = _parse_date(d.get("payment_date")) or datetime.today().date()
        notes = (d.get("notes") or "").strip() or None
        payment_id = str(uuid.uuid4())

        with transaction.atomic(), connection.cursor() as cur:
            # Verify booking belongs to tenant
            cur.execute(
                "SELECT id, total_amount, amount_paid FROM bookings WHERE id = %s AND tenant_id = %s FOR UPDATE",
                [booking_id, tenant_id],
            )
            row = cur.fetchone()
            if not row:
                return Response({"error": "Booking not found"}, status=status.HTTP_404_NOT_FOUND)

            total_amount = float(row[1] or 0)
            current_paid = float(row[2] or 0)
            new_paid = round(current_paid + amount, 2)

            # Determine new payment_status
            if new_paid <= 0:
                new_payment_status = "unpaid"
            elif new_paid >= total_amount:
                new_payment_status = "paid"
            else:
                new_payment_status = "partial"

            cur.execute(
                """
                INSERT INTO booking_payments (id, booking_id, amount, payment_method, payment_date, notes)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id, booking_id, amount, payment_method, payment_date, notes, created_at
                """,
                [payment_id, booking_id, amount, payment_method, payment_date, notes],
            )
            pay_cols = [c[0] for c in cur.description]
            payment = _serialize(cur.fetchone(), pay_cols)

            # Update booking amount_paid and payment_status
            cur.execute(
                """
                UPDATE bookings
                SET amount_paid = %s,
                    payment_status = %s::payment_status,
                    updated_at = NOW()
                WHERE id = %s AND tenant_id = %s
                """,
                [new_paid, new_payment_status, booking_id, tenant_id],
            )

        payment["new_payment_status"] = new_payment_status
        payment["new_amount_paid"] = new_paid
        return Response(payment, status=status.HTTP_201_CREATED)


class InvoiceList(APIView):
    """GET /api/invoices  POST /api/invoices"""

    def get(self, request):
        tenant_id = request.user.tenant_id
        with connection.cursor() as cur:
            cur.execute(
                """
                SELECT i.id, i.booking_id, i.invoice_number, i.amount,
                       i.status, i.issued_at, i.due_date, i.paid_at, i.notes,
                       b.guest_name, b.guest_email
                FROM invoices i
                JOIN bookings b ON b.id = i.booking_id
                WHERE b.tenant_id = %s
                ORDER BY i.issued_at DESC
                """,
                [tenant_id],
            )
            cols = [c[0] for c in cur.description]
            rows = [_serialize(r, cols) for r in cur.fetchall()]
        return Response(rows)

    def post(self, request):
        tenant_id = request.user.tenant_id
        d = request.data
        booking_id = d.get("booking_id")
        if not booking_id:
            return Response({"error": "booking_id required"}, status=status.HTTP_400_BAD_REQUEST)

        with connection.cursor() as cur:
            cur.execute(
                "SELECT id, total_amount FROM bookings WHERE id = %s AND tenant_id = %s",
                [booking_id, tenant_id],
            )
            row = cur.fetchone()
            if not row:
                return Response({"error": "Booking not found"}, status=status.HTTP_404_NOT_FOUND)
            total_amount = float(row[1] or 0)

            # Generate invoice number
            cur.execute(
                "SELECT COUNT(*) FROM invoices i JOIN bookings b ON b.id = i.booking_id WHERE b.tenant_id = %s",
                [tenant_id],
            )
            count = (cur.fetchone() or [0])[0] or 0
            invoice_number = f"INV-{int(count) + 1:04d}"

            amount = _safe_float(d.get("amount"), total_amount)
            due_date = _parse_date(d.get("due_date"))
            notes = (d.get("notes") or "").strip() or None
            invoice_id = str(uuid.uuid4())

            cur.execute(
                """
                INSERT INTO invoices (id, booking_id, invoice_number, amount, status, due_date, notes)
                VALUES (%s, %s, %s, %s, 'draft', %s, %s)
                RETURNING id, booking_id, invoice_number, amount, status, issued_at, due_date, paid_at, notes
                """,
                [invoice_id, booking_id, invoice_number, amount, due_date, notes],
            )
            cols = [c[0] for c in cur.description]
            invoice = _serialize(cur.fetchone(), cols)

        return Response(invoice, status=status.HTTP_201_CREATED)


class InvoiceDetail(APIView):
    """GET /api/invoices/{id}  PUT /api/invoices/{id}"""

    def get(self, request, invoice_id):
        tenant_id = request.user.tenant_id
        with connection.cursor() as cur:
            cur.execute(
                """
                SELECT i.id, i.booking_id, i.invoice_number, i.amount,
                       i.status, i.issued_at, i.due_date, i.paid_at, i.notes,
                       b.guest_name, b.guest_email, b.guest_phone,
                       b.check_in, b.check_out, b.guests, b.total_amount,
                       b.tax_amount, b.service_charge, b.base_amount,
                       r.name AS room_name,
                       t.name AS property_name, t.address, t.contact_email,
                       t.gst_percentage, t.gst_enabled
                FROM invoices i
                JOIN bookings b ON b.id = i.booking_id
                JOIN tenants t ON t.id = b.tenant_id
                LEFT JOIN rooms r ON r.id = b.room_id
                WHERE i.id = %s AND b.tenant_id = %s
                """,
                [invoice_id, tenant_id],
            )
            row = cur.fetchone()
            if not row:
                return Response({"error": "Invoice not found"}, status=status.HTTP_404_NOT_FOUND)
            cols = [c[0] for c in cur.description]
        return Response(_serialize(row, cols))

    def put(self, request, invoice_id):
        tenant_id = request.user.tenant_id
        d = request.data
        with connection.cursor() as cur:
            cur.execute(
                """
                UPDATE invoices SET
                    status = COALESCE(%s, status),
                    due_date = COALESCE(%s, due_date),
                    notes = COALESCE(%s, notes),
                    paid_at = CASE WHEN %s = 'paid' THEN NOW() ELSE paid_at END
                FROM bookings b
                WHERE invoices.booking_id = b.id
                  AND invoices.id = %s
                  AND b.tenant_id = %s
                RETURNING invoices.id, invoices.status
                """,
                [
                    d.get("status"),
                    _parse_date(d.get("due_date")),
                    d.get("notes"),
                    d.get("status"),
                    invoice_id,
                    tenant_id,
                ],
            )
            row = cur.fetchone()
            if not row:
                return Response({"error": "Invoice not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response({"success": True})
