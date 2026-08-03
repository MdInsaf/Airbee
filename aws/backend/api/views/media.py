import os
import uuid

import boto3
from django.db import connection
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from api.exceptions import safe_error_response
from api.permissions import IsStaff
from api.tenant_isolation import set_tenant_context

ALLOWED_CONTENT_TYPES = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}
MIN_CONTENT_LENGTH = 1024
MAX_CONTENT_LENGTH = 8 * 1024 * 1024
PRESIGN_EXPIRES_IN = 300


class MediaPresign(APIView):
    permission_classes = [IsStaff]

    def post(self, request):
        set_tenant_context(request)
        tenant_id = request.user.tenant_id

        context = (request.data.get("context") or "").strip()
        if context not in ("room", "hero"):
            return Response({"error": "context must be 'room' or 'hero'"}, status=status.HTTP_400_BAD_REQUEST)

        content_type = (request.data.get("content_type") or "").strip().lower()
        ext = ALLOWED_CONTENT_TYPES.get(content_type)
        if not ext:
            return Response(
                {"error": "content_type must be one of image/jpeg, image/png, image/webp"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if context == "room":
            room_id = (request.data.get("room_id") or "").strip()
            if not room_id:
                return Response({"error": "room_id is required for context=room"}, status=status.HTTP_400_BAD_REQUEST)
            with connection.cursor() as cur:
                cur.execute("SELECT id FROM rooms WHERE id = %s AND tenant_id = %s", [room_id, tenant_id])
                if not cur.fetchone():
                    return Response({"error": "Room not found"}, status=status.HTTP_404_NOT_FOUND)
            object_key = f"room-media/{tenant_id}/rooms/{room_id}/{uuid.uuid4()}.{ext}"
        else:
            object_key = f"room-media/{tenant_id}/hero/{uuid.uuid4()}.{ext}"

        bucket = os.environ.get("ROOM_MEDIA_BUCKET")
        public_base_url = os.environ.get("ROOM_MEDIA_PUBLIC_BASE_URL")
        if not bucket or not public_base_url:
            return Response(
                {"error": "Media storage is not configured on the server"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        try:
            region = os.environ.get("AWS_REGION", "ap-south-1")
            s3 = boto3.client(
                "s3",
                region_name=region,
                endpoint_url=f"https://s3.{region}.amazonaws.com",
            )
            presigned = s3.generate_presigned_post(
                Bucket=bucket,
                Key=object_key,
                Fields={"Content-Type": content_type},
                Conditions=[
                    {"Content-Type": content_type},
                    ["content-length-range", MIN_CONTENT_LENGTH, MAX_CONTENT_LENGTH],
                ],
                ExpiresIn=PRESIGN_EXPIRES_IN,
            )
        except Exception as exc:
            return safe_error_response(
                "Could not create upload URL",
                code="MEDIA_PRESIGN_FAILED",
                status_code=status.HTTP_502_BAD_GATEWAY,
                exc=exc,
            )

        return Response(
            {
                "upload_url": presigned["url"],
                "fields": presigned["fields"],
                "public_url": f"{public_base_url}/{object_key}",
                "object_key": object_key,
                "expires_in": PRESIGN_EXPIRES_IN,
            }
        )
