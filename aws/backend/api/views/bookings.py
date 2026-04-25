import uuid
from datetime import datetime
from decimal import Decimal
from django.db import connection, transaction
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status


ALLOWED_BOOKING_STATUS = {"pending", "confirmed", "cancelled", "completed"}
ALLOWED_PAYMENT_STATUS = {"unpaid", "partial", "paid"}


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


def _parse_date(raw_value):
    try:
        return datetime.strptime(str(raw_value), "%Y-%m-%d").date()
    except Exception:
        return None


def _safe_int(value, default=1):
    try:
        return int(value)
    except Exception:
        return default


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


def _normalize_uuid(raw_value):
    if raw_value in (None, ""):
        return None
    try:
        return str(uuid.UUID(str(raw_value)))
    except Exception:
        return None


class BookingList(APIView):
    def get(self, request):
        tenant_id = request.user.tenant_id
        with connection.cursor() as cur:
            cur.execute(
                """
                SELECT b.*,
                       r.name AS room_name,
                       r.base_price AS room_base_price
                FROM bookings b
                LEFT JOIN rooms r ON b.room_id = r.id
                WHERE b.tenant_id = %s
                ORDER BY b.created_at DESC
                """,
                [tenant_id],
            )
            cols = [c[0] for c in cur.description]
            rows = [_serialize(r, cols) for r in cur.fetchall()]
        return Response(rows)

    def post(self, request):
        tenant_id = request.user.tenant_id
        d = request.data
        room_id = _normalize_uuid(d.get("room_id"))
        guest_id = _normalize_uuid(d.get("guest_id")) if d.get("guest_id") else None
        guest_name = (d.get("guest_name") or "").strip()
        guest_email = (d.get("guest_email") or "").strip() or None
        guest_phone = (d.get("guest_phone") or "").strip() or None
        check_in = _parse_date(d.get("check_in"))
        check_out = _parse_date(d.get("check_out"))
        guests = max(1, _safe_int(d.get("guests"), 1))
        booking_status = str(d.get("status") or "pending").strip()
        payment_status = str(d.get("payment_status") or "unpaid").strip()

        if not room_id:
            return Response({"error": "Valid room_id is required"}, status=status.HTTP_400_BAD_REQUEST)
        if d.get("guest_id") and not guest_id:
            return Response({"error": "Valid guest_id is required"}, status=status.HTTP_400_BAD_REQUEST)
        if not guest_name:
            return Response({"error": "guest_name is required"}, status=status.HTTP_400_BAD_REQUEST)
        if not check_in or not check_out:
            return Response({"error": "check_in and check_out must be YYYY-MM-DD"}, status=status.HTTP_400_BAD_REQUEST)
        if check_out <= check_in:
            return Response({"error": "Check-out must be after check-in"}, status=status.HTTP_400_BAD_REQUEST)
        if booking_status not in ALLOWED_BOOKING_STATUS:
            return Response({"error": "Invalid booking status"}, status=status.HTTP_400_BAD_REQUEST)
        if payment_status not in ALLOWED_PAYMENT_STATUS:
            return Response({"error": "Invalid payment status"}, status=status.HTTP_400_BAD_REQUEST)

        booking_source = str(d.get("booking_source") or "direct").strip()
        booking_id = str(uuid.uuid4())
        with transaction.atomic(), connection.cursor() as cur:
            cur.execute(
                """
                SELECT id, max_guests, base_price, status
                FROM rooms
                WHERE id = %s AND tenant_id = %s
                FOR UPDATE
                """,
                [room_id, tenant_id],
            )
            room = cur.fetchone()
            if not room:
                return Response({"error": "Room not found"}, status=status.HTTP_404_NOT_FOUND)
            _, max_guests, base_price, room_status = room
            if room_status != "available":
                return Response({"error": "Room is not available for booking"}, status=status.HTTP_400_BAD_REQUEST)
            if guests > int(max_guests or 1):
                return Response({"error": "Selected room does not support that many guests"}, status=status.HTTP_400_BAD_REQUEST)

            if guest_id:
                cur.execute(
                    "SELECT 1 FROM guest_profiles WHERE id = %s AND tenant_id = %s LIMIT 1",
                    [guest_id, tenant_id],
                )
                if not cur.fetchone():
                    return Response({"error": "Guest not found"}, status=status.HTTP_404_NOT_FOUND)

            if booking_status in {"pending", "confirmed"}:
                cur.execute(
                    """
                    SELECT 1
                    FROM bookings
                    WHERE tenant_id = %s
                      AND room_id = %s
                      AND status IN ('pending', 'confirmed')
                      AND check_in < %s
                      AND check_out > %s
                    LIMIT 1
                    """,
                    [tenant_id, room_id, check_out, check_in],
                )
                if cur.fetchone():
                    return Response(
                        {"error": "Room is already booked for the selected dates"},
                        status=status.HTTP_409_CONFLICT,
                    )

            nights = (check_out - check_in).days
            total_amount = _safe_float(d.get("total_amount"), 0.0)
            if total_amount <= 0:
                total_amount = _safe_float(base_price) * nights

            cur.execute(
                """
                INSERT INTO bookings (
                    id, tenant_id, room_id, guest_id,
                    guest_name, guest_email, guest_phone,
                    check_in, check_out, guests,
                    total_amount, base_amount,
                    status, payment_status, notes, booking_source
                )
                VALUES (
                    %s,%s,%s,%s,
                    %s,%s,%s,
                    %s,%s,COALESCE(%s,1),
                    COALESCE(%s,0), COALESCE(%s,0),
                    COALESCE(%s,'pending')::booking_status,
                    COALESCE(%s,'unpaid')::payment_status,
                    %s, COALESCE(%s,'direct')
                )
                RETURNING id, tenant_id, room_id, guest_id, guest_name, guest_email, guest_phone,
                          check_in, check_out, guests, total_amount, base_amount, tax_amount,
                          service_charge, status, payment_status, payment_method, amount_paid,
                          notes, created_at, updated_at
                """,
                [
                    booking_id, tenant_id,
                    room_id, guest_id,
                    guest_name, guest_email, guest_phone,
                    check_in, check_out, guests,
                    total_amount, total_amount,
                    booking_status, payment_status,
                    d.get("notes"),
                    booking_source,
                ],
            )
            cols = [c[0] for c in cur.description]
            row = _serialize(cur.fetchone(), cols)
        return Response(row, status=status.HTTP_201_CREATED)


class BookingDetail(APIView):
    def put(self, request, booking_id):
        tenant_id = request.user.tenant_id
        d = request.data
        with connection.cursor() as cur:
            cur.execute(
                """
                UPDATE bookings SET
                    status = COALESCE(%s::booking_status, status),
                    payment_status = COALESCE(%s::payment_status, payment_status),
                    amount_paid = COALESCE(%s, amount_paid),
                    notes = COALESCE(%s, notes),
                    updated_at = NOW()
                WHERE id = %s AND tenant_id = %s
                RETURNING id, tenant_id, room_id, guest_id, guest_name, guest_email, guest_phone,
                          check_in, check_out, guests, total_amount, base_amount, tax_amount,
                          service_charge, status, payment_status, payment_method, amount_paid,
                          notes, created_at, updated_at
                """,
                [
                    d.get("status"), d.get("payment_status"),
                    d.get("amount_paid"), d.get("notes"),
                    booking_id, tenant_id,
                ],
            )
            row = cur.fetchone()
            if not row:
                return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)
            cols = [c[0] for c in cur.description]
        return Response(_serialize(row, cols))
