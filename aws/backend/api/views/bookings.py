import uuid
import logging
from datetime import datetime
from decimal import Decimal
from django.db import connection, transaction
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from api.idempotency import idempotent
from api.permissions import CanManageBookings
from api.tenant_isolation import set_tenant_context


logger = logging.getLogger("airbee.bookings")


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
    permission_classes = [CanManageBookings]

    def get(self, request):
        set_tenant_context(request)
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

    @idempotent("booking:create")
    def post(self, request):
        set_tenant_context(request)
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
    permission_classes = [CanManageBookings]

    def put(self, request, booking_id):
        set_tenant_context(request)
        tenant_id = request.user.tenant_id
        d = request.data
        new_status = d.get("status")
        new_room_id = _normalize_uuid(d.get("room_id")) if d.get("room_id") else None

        with transaction.atomic(), connection.cursor() as cur:
            if new_room_id:
                cur.execute(
                    "SELECT room_id, check_in, check_out, status, guests FROM bookings WHERE id = %s AND tenant_id = %s FOR UPDATE",
                    [booking_id, tenant_id],
                )
                current = cur.fetchone()
                if not current:
                    return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)
                cur_room_id, cur_check_in, cur_check_out, cur_status, cur_guests = current

                if str(cur_room_id) != new_room_id:
                    cur.execute(
                        "SELECT max_guests, status FROM rooms WHERE id = %s AND tenant_id = %s FOR UPDATE",
                        [new_room_id, tenant_id],
                    )
                    target = cur.fetchone()
                    if not target:
                        return Response({"error": "Target room not found"}, status=status.HTTP_404_NOT_FOUND)
                    target_max, target_status = target
                    if target_status != "available":
                        return Response({"error": "Target room is not available"}, status=status.HTTP_400_BAD_REQUEST)
                    if int(cur_guests or 1) > int(target_max or 1):
                        return Response({"error": "Target room cannot fit this many guests"}, status=status.HTTP_400_BAD_REQUEST)

                    if cur_status in ("pending", "confirmed"):
                        cur.execute(
                            """
                            SELECT 1 FROM bookings
                            WHERE tenant_id = %s
                              AND room_id = %s
                              AND id != %s
                              AND status IN ('pending', 'confirmed')
                              AND check_in < %s AND check_out > %s
                            LIMIT 1
                            """,
                            [tenant_id, new_room_id, booking_id, cur_check_out, cur_check_in],
                        )
                        if cur.fetchone():
                            return Response(
                                {"error": "Target room is already booked for these dates"},
                                status=status.HTTP_409_CONFLICT,
                            )

            cur.execute(
                """
                UPDATE bookings SET
                    status = COALESCE(%s::booking_status, status),
                    payment_status = COALESCE(%s::payment_status, payment_status),
                    amount_paid = COALESCE(%s, amount_paid),
                    notes = COALESCE(%s, notes),
                    room_id = COALESCE(%s, room_id),
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
                    new_room_id,
                    booking_id, tenant_id,
                ],
            )
            row = cur.fetchone()
            if not row:
                return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)
            cols = [c[0] for c in cur.description]
            booking = _serialize(row, cols)

        if new_status == "confirmed":
            try:
                from api.views.email_utils import send_booking_confirmed_email
                with connection.cursor() as cur:
                    cur.execute(
                        """
                        SELECT r.name, t.name, t.contact_email, t.contact_phone,
                               t.address, t.currency, t.primary_hostname
                        FROM bookings b
                        LEFT JOIN rooms r ON r.id = b.room_id
                        JOIN tenants t ON t.id = b.tenant_id
                        WHERE b.id = %s
                        """,
                        [booking_id],
                    )
                    meta = cur.fetchone()
                if meta:
                    room_name, prop_name, c_email, c_phone, address, currency, hostname = meta
                    send_booking_confirmed_email(
                        tenant_id,
                        booking=booking,
                        room_name=room_name or "—",
                        property_data={
                            "name": prop_name or "",
                            "contact_email": c_email or "",
                            "contact_phone": c_phone or "",
                            "address": address or "",
                            "currency": currency or "INR",
                            "primary_hostname": hostname or "",
                        },
                    )
            except Exception:
                logger.exception(
                    "booking_confirmation_email_failed",
                    extra={"entity_type": "bookings", "entity_id": str(booking_id)},
                )

        return Response(booking)


def _create_one_booking(cur, tenant_id, item):
    """Run the same validations as BookingList.post for a single dict.
    Returns (status_code, payload_dict). Caller manages the transaction."""
    room_id = _normalize_uuid(item.get("room_id"))
    guest_id = _normalize_uuid(item.get("guest_id")) if item.get("guest_id") else None
    guest_name = (item.get("guest_name") or "").strip()
    guest_email = (item.get("guest_email") or "").strip() or None
    guest_phone = (item.get("guest_phone") or "").strip() or None
    check_in = _parse_date(item.get("check_in"))
    check_out = _parse_date(item.get("check_out"))
    guests = max(1, _safe_int(item.get("guests"), 1))
    booking_status = str(item.get("status") or "pending").strip()
    payment_status = str(item.get("payment_status") or "unpaid").strip()
    booking_source = str(item.get("booking_source") or "direct").strip()

    if not room_id:
        return 400, {"error": "Valid room_id is required"}
    if item.get("guest_id") and not guest_id:
        return 400, {"error": "Valid guest_id is required"}
    if not guest_name:
        return 400, {"error": "guest_name is required"}
    if not check_in or not check_out:
        return 400, {"error": "check_in and check_out must be YYYY-MM-DD"}
    if check_out <= check_in:
        return 400, {"error": "Check-out must be after check-in"}
    if booking_status not in ALLOWED_BOOKING_STATUS:
        return 400, {"error": "Invalid booking status"}
    if payment_status not in ALLOWED_PAYMENT_STATUS:
        return 400, {"error": "Invalid payment status"}

    cur.execute(
        "SELECT id, max_guests, base_price, status FROM rooms WHERE id = %s AND tenant_id = %s FOR UPDATE",
        [room_id, tenant_id],
    )
    room = cur.fetchone()
    if not room:
        return 404, {"error": f"Room {room_id} not found"}
    _, max_guests, base_price, room_status = room
    if room_status != "available":
        return 400, {"error": f"Room {room_id} is not available for booking"}
    if guests > int(max_guests or 1):
        return 400, {"error": f"Room {room_id} does not support {guests} guests"}

    if booking_status in {"pending", "confirmed"}:
        cur.execute(
            """
            SELECT 1 FROM bookings
            WHERE tenant_id = %s AND room_id = %s
              AND status IN ('pending', 'confirmed')
              AND check_in < %s AND check_out > %s
            LIMIT 1
            """,
            [tenant_id, room_id, check_out, check_in],
        )
        if cur.fetchone():
            return 409, {"error": f"Room {room_id} is already booked for {check_in}–{check_out}"}

    nights = (check_out - check_in).days
    total_amount = _safe_float(item.get("total_amount"), 0.0)
    if total_amount <= 0:
        total_amount = _safe_float(base_price) * nights

    booking_id = str(uuid.uuid4())
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
            booking_id, tenant_id, room_id, guest_id,
            guest_name, guest_email, guest_phone,
            check_in, check_out, guests,
            total_amount, total_amount,
            booking_status, payment_status,
            item.get("notes"), booking_source,
        ],
    )
    cols = [c[0] for c in cur.description]
    return 201, _serialize(cur.fetchone(), cols)


class BookingBulkCreate(APIView):
    """POST /api/bookings/bulk - body: { "bookings": [ {...}, {...} ] }
    All-or-nothing: if any row fails validation, none are created.
    """

    permission_classes = [CanManageBookings]

    @idempotent("booking:bulk-create")
    def post(self, request):
        set_tenant_context(request)
        tenant_id = request.user.tenant_id
        items = request.data.get("bookings")
        if not isinstance(items, list) or not items:
            return Response({"error": "bookings must be a non-empty list"}, status=status.HTTP_400_BAD_REQUEST)
        if len(items) > 200:
            return Response({"error": "Cannot bulk-create more than 200 bookings at once"}, status=status.HTTP_400_BAD_REQUEST)

        created = []
        try:
            with transaction.atomic(), connection.cursor() as cur:
                for idx, item in enumerate(items):
                    if not isinstance(item, dict):
                        raise ValueError(f"Row {idx + 1}: invalid format")
                    code, payload = _create_one_booking(cur, tenant_id, item)
                    if code >= 400:
                        raise ValueError(f"Row {idx + 1}: {payload.get('error', 'invalid')}")
                    created.append(payload)
        except ValueError as ve:
            return Response({"error": str(ve)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            return Response({"error": f"Bulk create failed: {exc}"}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"created": created, "count": len(created)}, status=status.HTTP_201_CREATED)
