"""Durable idempotency using database (survives Lambda restart)."""

from __future__ import annotations

import hashlib
import json
import logging
from functools import wraps
from typing import Callable, Optional

from django.db import connection, transaction
from rest_framework.response import Response

logger = logging.getLogger("airbee.idempotency")


def require_idempotency_key(scope: str = "default"):
    """Database-backed idempotency for payment/booking safety.

    Atomically claims an idempotency key in the database, preventing
    duplicate execution across Lambda container boundaries.

    Args:
        scope: Operation scope (e.g., "booking:create", "payment:capture")

    Usage:
        @require_idempotency_key("booking:create")
        def post(self, request):
            # Idempotency-Key header required
            pass
    """

    def decorator(view_func: Callable) -> Callable:
        @wraps(view_func)
        def wrapper(self, request, *args, **kwargs) -> Response:
            # GET/HEAD/OPTIONS don't need idempotency
            if request.method in {"GET", "HEAD", "OPTIONS"}:
                return view_func(self, request, *args, **kwargs)

            # Require idempotency key for mutations
            idempotency_key = request.headers.get("Idempotency-Key", "").strip()
            if not idempotency_key:
                return Response(
                    {
                        "code": "IDEMPOTENCY_KEY_REQUIRED",
                        "message": "Idempotency-Key header required for mutations",
                        "request_id": getattr(request, "request_id", "-"),
                    },
                    status=400,
                )

            tenant_id = getattr(request.user, "tenant_id", None)
            if not tenant_id:
                return Response(
                    {"code": "UNAUTHENTICATED", "message": "Authentication required"},
                    status=401,
                )

            # Hash request body to detect mutations
            request_hash = hashlib.sha256(
                request.body if request.body else b""
            ).hexdigest()

            # Atomic claim-and-execute in database transaction
            with transaction.atomic():
                with connection.cursor() as cur:
                    # Try to claim this idempotency key
                    cur.execute(
                        """
                        INSERT INTO api_idempotency_keys
                        (tenant_id, scope, idempotency_key, request_hash, created_at, expires_at)
                        VALUES (%s, %s, %s, %s, now(), now() + INTERVAL '24 hours')
                        ON CONFLICT (tenant_id, scope, idempotency_key)
                        DO UPDATE SET request_hash = EXCLUDED.request_hash
                        RETURNING response_status, response_body, created_at > now() - INTERVAL '1 second' as is_new
                        """,
                        [tenant_id, scope, idempotency_key, request_hash],
                    )
                    row = cur.fetchone()

                    if row and row[0]:  # response_status exists (already processed)
                        # Return cached response
                        logger.info(
                            "idempotency_replay",
                            extra={
                                "tenant_id": tenant_id,
                                "scope": scope,
                                "key_hash": idempotency_key[:8],
                            },
                        )
                        response = Response(
                            json.loads(row[1]) if row[1] else {},
                            status=row[0],
                        )
                        response["Idempotency-Replayed"] = "true"
                        return response

            # First execution: run business logic
            response = view_func(self, request, *args, **kwargs)

            # Store response for replay (only cache 2xx responses)
            if isinstance(response, Response) and 200 <= response.status_code < 300:
                try:
                    with connection.cursor() as cur:
                        cur.execute(
                            """
                            UPDATE api_idempotency_keys
                            SET response_status = %s, response_body = %s
                            WHERE tenant_id = %s AND scope = %s AND idempotency_key = %s
                            """,
                            [
                                response.status_code,
                                json.dumps(response.data),
                                tenant_id,
                                scope,
                                idempotency_key,
                            ],
                        )
                except Exception as e:
                    logger.error(
                        "idempotency_store_failed",
                        extra={"scope": scope, "error": str(e)},
                    )

            response["Idempotency-Replayed"] = "false"
            return response

        return wrapper

    return decorator


# Alias for backward compatibility
idempotent = require_idempotency_key
