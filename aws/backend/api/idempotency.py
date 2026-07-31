"""Idempotency key handling for safe request replay (payments, bookings, etc.)."""

from __future__ import annotations

import hashlib
import logging
from functools import wraps
from typing import Any, Callable, Optional, Union

from django.core.cache import cache
from django.http import HttpRequest
from rest_framework.response import Response

logger = logging.getLogger("airbee.idempotency")

DEFAULT_MAX_AGE_SECONDS = 86400  # 24 hours


class IdempotencyError(ValueError):
    pass


def _idempotency_cache_key(tenant_id: str, idempotency_key: str) -> str:
    """Build cache key for idempotency result storage."""
    return f"idempotency:{tenant_id}:{hashlib.sha256(idempotency_key.encode()).hexdigest()}"


def require_idempotency_key(scope: Union[str, Callable, None] = None, max_age_seconds: int = DEFAULT_MAX_AGE_SECONDS):
    """Decorator: require Idempotency-Key header for POST/PUT/PATCH/DELETE requests.

    Caches response and returns it if the same key is retried within max_age_seconds.
    Prevents double charges, duplicate bookings, etc.

    Args:
        scope: Optional string or callable to identify this operation for logging.
               If callable, receives (self, request, *args, **kwargs) and should return a string.
        max_age_seconds: Cache TTL for idempotency responses (default: 24 hours)

    Usage:
        @require_idempotency_key("booking:create")
        def post(self, request):
            return Response({"id": "..."}, status=201)

        @require_idempotency_key(lambda self, request, booking_id: f"booking:{booking_id}:payment")
        def post(self, request, booking_id):
            pass
    """
    # Handle decorator called without parentheses
    if callable(scope) and not isinstance(scope, str):
        view_func = scope
        scope = None
        return require_idempotency_key(None, max_age_seconds)(view_func)

    def decorator(view_func: Callable) -> Callable:
        @wraps(view_func)
        def wrapper(self: Any, request: HttpRequest, *args: Any, **kwargs: Any) -> Response:
            idempotency_key = request.headers.get("Idempotency-Key", "").strip()

            # GET/HEAD/OPTIONS don't need idempotency keys
            if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
                return view_func(self, request, *args, **kwargs)

            # Require idempotency key for mutations
            if not idempotency_key:
                return Response(
                    {
                        "code": "IDEMPOTENCY_KEY_REQUIRED",
                        "message": "Idempotency-Key header is required for this operation",
                        "request_id": getattr(request, "request_id", "-"),
                    },
                    status=400,
                )

            # Validate key format (printable ASCII, reasonable length)
            if not (1 <= len(idempotency_key) <= 256) or not idempotency_key.isprintable():
                return Response(
                    {
                        "code": "INVALID_IDEMPOTENCY_KEY",
                        "message": "Idempotency-Key must be 1-256 printable ASCII characters",
                        "request_id": getattr(request, "request_id", "-"),
                    },
                    status=400,
                )

            tenant_id = getattr(request.user, "tenant_id", "unknown")
            cache_key = _idempotency_cache_key(tenant_id, idempotency_key)

            # Compute operation scope for logging
            operation_scope = scope
            if callable(scope):
                try:
                    operation_scope = scope(self, request, *args, **kwargs)
                except Exception:
                    operation_scope = "unknown"

            # Check if this idempotency key was already processed
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                logger.info(
                    "idempotency_cache_hit",
                    extra={
                        "tenant_id": tenant_id,
                        "scope": operation_scope,
                        "key_hash": hashlib.sha256(idempotency_key.encode()).hexdigest()[:8],
                        "method": request.method,
                    },
                )
                return Response(cached_result["data"], status=cached_result["status"])

            # Process the request
            response = view_func(self, request, *args, **kwargs)

            # Cache successful responses (2xx) for replay
            if isinstance(response, Response) and 200 <= response.status_code < 300:
                cache.set(
                    cache_key,
                    {
                        "data": response.data,
                        "status": response.status_code,
                    },
                    max_age_seconds,
                )
                logger.info(
                    "idempotency_cached",
                    extra={
                        "tenant_id": tenant_id,
                        "scope": operation_scope,
                        "key_hash": hashlib.sha256(idempotency_key.encode()).hexdigest()[:8],
                        "method": request.method,
                        "status": response.status_code,
                    },
                )

            return response

        return wrapper

    return decorator

# Alias for convenience
idempotent = require_idempotency_key
