import uuid
from datetime import datetime, timezone, date
from decimal import Decimal

import requests
from django.db import connection
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response

try:
    from icalendar import Calendar
    ICAL_AVAILABLE = True
except ImportError:
    ICAL_AVAILABLE = False

ALLOWED_PLATFORMS = {"airbnb", "bookingcom", "expedia", "makemytrip", "other"}


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
    def get(self, request):
        tenant_id = _get_tenant_id(request)
        with connection.cursor() as cur:
            cur.execute(
                """
                SELECT c.id, c.name, c.platform, c.room_id, r.name AS room_name,
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

        with connection.cursor() as cur:
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
    def delete(self, request, channel_id):
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
    def post(self, request, channel_id):
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
            resp = requests.get(ical_url, timeout=15)
            resp.raise_for_status()
            cal = Calendar.from_ical(resp.content)
        except Exception as exc:
            with connection.cursor() as cur:
                cur.execute(
                    "UPDATE channels SET sync_status='error', sync_error=%s, last_synced_at=now() WHERE id=%s",
                    [str(exc), channel_id],
                )
            return Response({"error": f"Failed to fetch iCal: {exc}"}, status=400)

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

            with connection.cursor() as cur:
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
                    INSERT INTO bookings
                      (tenant_id, room_id, guest_name, check_in, check_out,
                       status, source_channel, external_uid, guests)
                    VALUES (%s, %s, %s, %s, %s, 'confirmed', %s, %s, 1)
                    ON CONFLICT DO NOTHING
                    """,
                    [tenant_id, room_id, summary, check_in, check_out, ch_name, uid],
                )
                created += 1

        with connection.cursor() as cur:
            cur.execute(
                "UPDATE channels SET sync_status='success', sync_error=NULL, last_synced_at=now() WHERE id=%s",
                [channel_id],
            )

        return Response({"synced": created, "skipped": skipped})


class ChannelICalExport(APIView):
    """Export bookings for a room as an iCal feed (no auth required)."""
    authentication_classes = []
    permission_classes = []

    def get(self, request, tenant_slug, room_id):
        with connection.cursor() as cur:
            cur.execute("SELECT id, name FROM tenants WHERE slug=%s", [tenant_slug])
            tenant_row = cur.fetchone()
            if not tenant_row:
                return Response({"error": "Not found"}, status=404)
            tenant_id, tenant_name = tenant_row

            cur.execute(
                "SELECT id, name FROM rooms WHERE id=%s AND tenant_id=%s",
                [room_id, tenant_id],
            )
            room_row = cur.fetchone()
            if not room_row:
                return Response({"error": "Room not found"}, status=404)
            _, room_name = room_row

            cur.execute(
                """
                SELECT id, guest_name, check_in, check_out
                FROM bookings
                WHERE tenant_id=%s AND room_id=%s AND status NOT IN ('cancelled')
                ORDER BY check_in
                """,
                [tenant_id, room_id],
            )
            bookings = cur.fetchall()

        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            f"PRODID:-//Airbee//{tenant_name}//EN",
            f"X-WR-CALNAME:{room_name} Bookings",
        ]
        for b_id, guest_name, check_in, check_out in bookings:
            lines += [
                "BEGIN:VEVENT",
                f"UID:{b_id}@airbee",
                f"SUMMARY:Booking - {guest_name}",
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
            headers={"Content-Disposition": f'attachment; filename="{room_name}.ics"'},
        )
