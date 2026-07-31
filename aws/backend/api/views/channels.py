import uuid
from datetime import datetime, timezone, date
from decimal import Decimal

from django.db import connection, transaction
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response

from api.network_security import SafeFetchError, fetch_ical
from api.permissions import IsStaff
from api.tenant_isolation import set_tenant_context

try:
    from icalendar import Calendar
    ICAL_AVAILABLE = True
except ImportError:
    ICAL_AVAILABLE = False

ALLOWED_PLATFORMS = {"airbnb", "bookingcom", "expedia", "makemytrip", "other"}


def _ical_escape(value):
    return (
        str(value or "")
        .replace("\\", "\\\\")
        .replace("\r", "")
        .replace("\n", "\\n")
        .replace(",", "\\,")
        .replace(";", "\\;")
    )


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


def _get_tenant_id(request):
    return request.user.tenant_id


class ChannelList(APIView):
    permission_classes = [IsStaff]

    def get(self, request):
        set_tenant_context(request)
        tenant_id = _get_tenant_id(request)
        with connection.cursor() as cur:
            cur.execute(
                """
                SELECT c.id, c.name, c.platform, c.room_id, r.name AS room_name,
                       r.ical_feed_token,
                       c.ical_url, c.last_synced_at, c.sync_status, c.sync_error, c.created_at
                FROM channels c
                LEFT JOIN rooms r ON r.id = c.room_id
                WHERE c.tenant_id = %s
                ORDER BY c.created_at DESC
                """,
                [tenant_id],
            )
            cols = [c[0] for c in cur.description]
            channels = [_serialize(row, cols) for row in cur.fetchall()]
        return Response({"channels": channels})

    def post(self, request):
        set_tenant_context(request)
        tenant_id = _get_tenant_id(request)
        data = request.data
        name = (data.get("name") or "").strip()
        platform = (data.get("platform") or "other").strip().lower()
        room_id = (data.get("room_id") or "").strip() or None
        ical_url = (data.get("ical_url") or "").strip() or None

        if not name:
            return Response({"error": "name is required"}, status=400)
        if platform not in ALLOWED_PLATFORMS:
            platform = "other"
        if room_id:
            try:
                room_id = str(uuid.UUID(room_id))
            except Exception:
                return Response({"error": "Valid room_id is required"}, status=400)

        with connection.cursor() as cur:
            if room_id:
                cur.execute(
                    "SELECT 1 FROM rooms WHERE id = %s AND tenant_id = %s LIMIT 1",
                    [room_id, tenant_id],
                )
                if not cur.fetchone():
                    return Response({"error": "Room not found"}, status=404)

            cur.execute(
                """
                INSERT INTO channels (tenant_id, name, platform, room_id, ical_url)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id, name, platform, room_id, ical_url, last_synced_at,
                          sync_status, sync_error, created_at
                """,
                [tenant_id, name, platform, room_id, ical_url],
            )
            cols = [c[0] for c in cur.description]
            channel = _serialize(cur.fetchone(), cols)
        return Response({"channel": channel}, status=status.HTTP_201_CREATED)


class ChannelDetail(APIView):
    permission_classes = [IsStaff]

    def delete(self, request, channel_id):
        set_tenant_context(request)
        tenant_id = _get_tenant_id(request)
        with connection.cursor() as cur:
            cur.execute(
                "DELETE FROM channels WHERE id = %s AND tenant_id = %s RETURNING id",
                [channel_id, tenant_id],
            )
            if not cur.fetchone():
                return Response({"error": "Not found"}, status=404)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ChannelSync(APIView):
    permission_classes = [IsStaff]

    def post(self, request, channel_id):
        set_tenant_context(request)
        tenant_id = _get_tenant_id(request)

        if not ICAL_AVAILABLE:
            return Response({"error": "icalendar library not installed"}, status=500)

        with connection.cursor() as cur:
            cur.execute(
                "SELECT id, room_id, ical_url, name FROM channels WHERE id = %s AND tenant_id = %s",
                [channel_id, tenant_id],
            )
            row = cur.fetchone()
            if not row:
                return Response({"error": "Channel not found"}, status=404)
            ch_id, room_id, ical_url, ch_name = row

        if not ical_url:
            return Response({"error": "No iCal URL configured for this channel"}, status=400)
        if not room_id:
            return Response({"error": "No room linked to this channel"}, status=400)

        try:
            cal = Calendar.from_ical(fetch_ical(ical_url))
        except SafeFetchError as exc:
            with connection.cursor() as cur:
                cur.execute(
                    "UPDATE channels SET sync_status='error', sync_error=%s, last_synced_at=now() WHERE id=%s",
                    [str(exc), channel_id],
                )
            return Response({"error": f"Failed to fetch iCal: {exc}"}, status=400)
        except Exception:
            with connection.cursor() as cur:
                cur.execute(
                    "UPDATE channels SET sync_status='error', sync_error=%s, last_synced_at=now() WHERE id=%s",
                    ["The iCal response could not be parsed", channel_id],
                )
            return Response({"error": "The iCal response could not be parsed"}, status=400)

        created = 0
        skipped = 0
        for component in cal.walk():
            if component.name != "VEVENT":
                continue

            uid = str(component.get("uid", ""))
            summary = str(component.get("summary", ch_name))
            dtstart = component.get("dtstart")
            dtend = component.get("dtend")

            if not dtstart or not dtend:
                continue

            check_in = dtstart.dt if isinstance(dtstart.dt, date) else dtstart.dt.date()
            check_out = dtend.dt if isinstance(dtend.dt, date) else dtend.dt.date()

            if check_out <= check_in:
                continue

            with transaction.atomic(), connection.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM rooms WHERE id=%s AND tenant_id=%s FOR UPDATE",
                    [room_id, tenant_id],
                )

                # Skip if already imported
                cur.execute(
                    "SELECT id FROM bookings WHERE tenant_id=%s AND room_id=%s AND external_uid=%s",
                    [tenant_id, room_id, uid],
                )
                if cur.fetchone():
                    skipped += 1
                    continue

                cur.execute(
                    """
                    SELECT 1
                    FROM bookings
                    WHERE tenant_id=%s
                      AND room_id=%s
                      AND status IN ('pending', 'confirmed')
                      AND check_in < %s
                      AND check_out > %s
                    LIMIT 1
                    """,
                    [tenant_id, room_id, check_out, check_in],
                )
                if cur.fetchone():
                    skipped += 1
                    continue

                cur.execute(
                    """
                    INSERT INTO bookings
                      (tenant_id, room_id, guest_name, check_in, check_out,
                       status, source_channel, external_uid, guests)
                    VALUES (%s, %s, %s, %s, %s, 'confirmed', %s, %s, 1)
                    ON CONFLICT DO NOTHING
                    """,
                    [tenant_id, room_id, summary, check_in, check_out, ch_name, uid],
                )
                created += cur.rowcount

        with connection.cursor() as cur:
            cur.execute(
                "UPDATE channels SET sync_status='success', sync_error=NULL, last_synced_at=now() WHERE id=%s",
                [channel_id],
            )

        return Response({"synced": created, "skipped": skipped})


class ChannelICalExport(APIView):
    """Export availability through an unguessable, revocable room token."""
    authentication_classes = []
    permission_classes = []
    throttle_scope = "ical_export"

    def get(self, request, feed_token):
        set_tenant_context(request)
        with connection.cursor() as cur:
            cur.execute(
                """
                SELECT r.id, r.name, r.tenant_id, t.name
                FROM rooms r
                JOIN tenants t ON t.id = r.tenant_id
                WHERE r.ical_feed_token = %s
                """,
                [str(feed_token)],
            )
            room_row = cur.fetchone()
            if not room_row:
                return Response({"error": "Not found"}, status=404)
            room_id, room_name, tenant_id, tenant_name = room_row

            cur.execute(
                """
                SELECT id, check_in, check_out
                FROM bookings
                WHERE tenant_id=%s AND room_id=%s AND status NOT IN ('cancelled')
                ORDER BY check_in
                """,
                [tenant_id, room_id],
            )
            bookings = cur.fetchall()

        safe_tenant_name = _ical_escape(tenant_name)
        safe_room_name = _ical_escape(room_name)
        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            f"PRODID:-//Airbee//{safe_tenant_name}//EN",
            f"X-WR-CALNAME:{safe_room_name} Bookings",
        ]
        for b_id, check_in, check_out in bookings:
            lines += [
                "BEGIN:VEVENT",
                f"UID:{b_id}@airbee",
                "SUMMARY:Unavailable",
                f"DTSTART;VALUE=DATE:{check_in.strftime('%Y%m%d')}",
                f"DTEND;VALUE=DATE:{check_out.strftime('%Y%m%d')}",
                f"DTSTAMP:{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
                "END:VEVENT",
            ]
        lines.append("END:VCALENDAR")

        from django.http import HttpResponse
        return HttpResponse(
            "\r\n".join(lines),
            content_type="text/calendar; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="airbee-room.ics"'},
        )


class ChannelICalRotate(APIView):
    permission_classes = [IsStaff]
    """Rotate a room feed token to revoke previously shared URLs."""

    def post(self, request, room_id):
        set_tenant_context(request)
        tenant_id = _get_tenant_id(request)
        try:
            normalized_room_id = str(uuid.UUID(str(room_id)))
        except ValueError:
            return Response({"error": "Room not found"}, status=404)

        new_token = str(uuid.uuid4())
        with connection.cursor() as cur:
            cur.execute(
                """
                UPDATE rooms
                SET ical_feed_token = %s, updated_at = now()
                WHERE id = %s AND tenant_id = %s
                RETURNING ical_feed_token
                """,
                [new_token, normalized_room_id, tenant_id],
            )
            row = cur.fetchone()
        if not row:
            return Response({"error": "Room not found"}, status=404)
        return Response({"room_id": normalized_room_id, "ical_feed_token": str(row[0])})
