import json
import uuid
from decimal import Decimal
from django.db import connection
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from api.exceptions import safe_error_response
from api.permissions import IsStaff
from api.tenant_isolation import set_tenant_context

ALLOWED_ROOM_STATUS = {"available", "maintenance", "unavailable"}
ALLOWED_HOUSEKEEPING_STATUS = {"clean", "dirty", "in_progress", "inspecting"}
MAX_ROOM_IMAGES = 12


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


def _safe_int(value, default):
    try:
        return int(value)
    except Exception:
        return default


def _safe_float(value, default):
    try:
        return float(value)
    except Exception:
        return default


def _payload_string(data, key, partial=False):
    if partial and key not in data:
        return None
    return (data.get(key) or "").strip()


IMAGES_INVALID = object()


def _normalize_images(value):
    if not isinstance(value, list):
        return IMAGES_INVALID
    urls = []
    for item in value:
        if not isinstance(item, str):
            return IMAGES_INVALID
        url = item.strip()
        if not url:
            continue
        if len(url) > 2048 or not url.startswith(("https://", "http://")):
            return IMAGES_INVALID
        urls.append(url)
    return urls[:MAX_ROOM_IMAGES]


def _normalize_room_payload(data, partial=False):
    has_name = "name" in data or not partial
    has_description = "description" in data or not partial
    has_category_id = "category_id" in data or not partial
    has_max_guests = "max_guests" in data or not partial
    has_base_price = "base_price" in data or not partial
    has_status = "status" in data or not partial
    has_housekeeping_status = "housekeeping_status" in data or not partial
    has_images = "images" in data

    return {
        "name": _payload_string(data, "name", partial) if has_name else None,
        "description": (_payload_string(data, "description", partial) or None) if has_description else None,
        "category_id": (_payload_string(data, "category_id", partial) or None) if has_category_id else None,
        "max_guests": max(1, _safe_int(data.get("max_guests"), 2)) if has_max_guests else None,
        "base_price": max(0.0, _safe_float(data.get("base_price"), 0.0)) if has_base_price else None,
        "status": (_payload_string(data, "status", partial) or None) if has_status else None,
        "housekeeping_status": (
            _payload_string(data, "housekeeping_status", partial) or None
        ) if has_housekeeping_status else None,
        "images": _normalize_images(data.get("images")) if has_images else None,
    }


class RoomList(APIView):
    permission_classes = [IsStaff]

    def get(self, request):
        set_tenant_context(request)
        tenant_id = request.user.tenant_id
        with connection.cursor() as cur:
            cur.execute(
                """
                SELECT r.id, r.name, r.description, r.category_id,
                       r.max_guests, r.base_price, r.status, r.housekeeping_status,
                       r.amenities, r.images, r.ical_feed_token, r.created_at
                FROM rooms r
                WHERE r.tenant_id = %s
                ORDER BY r.created_at DESC
                """,
                [tenant_id],
            )
            cols = [c[0] for c in cur.description]
            rows = [_serialize(r, cols) for r in cur.fetchall()]
        return Response(rows)

    def post(self, request):
        set_tenant_context(request)
        tenant_id = request.user.tenant_id
        d = _normalize_room_payload(request.data)
        if not d["name"]:
            return Response({"error": "Room name is required"}, status=status.HTTP_400_BAD_REQUEST)
        if d["status"] and d["status"] not in ALLOWED_ROOM_STATUS:
            return Response({"error": "Invalid room status"}, status=status.HTTP_400_BAD_REQUEST)
        if d["housekeeping_status"] and d["housekeeping_status"] not in ALLOWED_HOUSEKEEPING_STATUS:
            return Response({"error": "Invalid housekeeping status"}, status=status.HTTP_400_BAD_REQUEST)

        count = max(1, min(500, _safe_int(request.data.get("count"), 1)))
        start_number = _safe_int(request.data.get("start_number"), 1)
        # When bulk-creating, the supplied "name" acts as the prefix unless name_prefix overrides it.
        prefix = (request.data.get("name_prefix") or d["name"]).strip() if count > 1 else d["name"]

        try:
            with connection.cursor() as cur:
                created_ids = []
                for i in range(count):
                    room_id = str(uuid.uuid4())
                    if count > 1:
                        room_name = f"{prefix} {start_number + i}".strip()
                    else:
                        room_name = d["name"]
                    cur.execute(
                        """
                        INSERT INTO rooms (id, tenant_id, name, description, category_id,
                                           max_guests, base_price, status, housekeeping_status)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,
                                COALESCE(%s,'available')::room_status,
                                COALESCE(%s,'clean')::housekeeping_status)
                        """,
                        [
                            room_id,
                            tenant_id,
                            room_name,
                            d["description"],
                            d["category_id"],
                            d["max_guests"],
                            d["base_price"],
                            d["status"],
                            d["housekeeping_status"],
                        ],
                    )
                    created_ids.append(room_id)
        except Exception as exc:
            return safe_error_response(
                "Could not create room",
                code="ROOM_CREATE_FAILED",
                exc=exc,
            )

        if count > 1:
            return Response({"created": created_ids, "count": count}, status=status.HTTP_201_CREATED)
        return Response({"id": created_ids[0]}, status=status.HTTP_201_CREATED)


class RoomDetail(APIView):
    permission_classes = [IsStaff]

    def put(self, request, room_id):
        set_tenant_context(request)
        tenant_id = request.user.tenant_id
        d = _normalize_room_payload(request.data, partial=True)
        if d["status"] and d["status"] not in ALLOWED_ROOM_STATUS:
            return Response({"error": "Invalid room status"}, status=status.HTTP_400_BAD_REQUEST)
        if d["housekeeping_status"] and d["housekeeping_status"] not in ALLOWED_HOUSEKEEPING_STATUS:
            return Response({"error": "Invalid housekeeping status"}, status=status.HTTP_400_BAD_REQUEST)
        if d["images"] is IMAGES_INVALID:
            return Response(
                {"error": "images must be a list of http(s) URLs"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        images_json = json.dumps(d["images"]) if d["images"] is not None else None
        try:
            with connection.cursor() as cur:
                cur.execute(
                    """
                    UPDATE rooms SET
                        name = COALESCE(%s, name),
                        description = COALESCE(%s, description),
                        category_id = COALESCE(%s, category_id),
                        max_guests = COALESCE(%s, max_guests),
                        status = COALESCE(%s, status),
                        housekeeping_status = COALESCE(%s, housekeeping_status),
                        base_price = COALESCE(%s, base_price),
                        images = COALESCE(%s::jsonb, images),
                        updated_at = NOW()
                    WHERE id = %s AND tenant_id = %s
                    """,
                    [
                        d["name"] or None,
                        d["description"],
                        d["category_id"],
                        d["max_guests"],
                        d["status"],
                        d["housekeeping_status"],
                        d["base_price"],
                        images_json,
                        room_id,
                        tenant_id,
                    ],
                )
        except Exception as exc:
            return safe_error_response(
                "Could not update room",
                code="ROOM_UPDATE_FAILED",
                exc=exc,
            )
        return Response({"success": True})

    def delete(self, request, room_id):
        set_tenant_context(request)
        tenant_id = request.user.tenant_id
        with connection.cursor() as cur:
            cur.execute(
                "DELETE FROM rooms WHERE id = %s AND tenant_id = %s",
                [room_id, tenant_id],
            )
        return Response(status=status.HTTP_204_NO_CONTENT)
