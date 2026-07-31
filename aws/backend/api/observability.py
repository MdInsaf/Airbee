"""Structured request logging and correlation context for Lambda/CloudWatch."""

from __future__ import annotations

import contextvars
import json
import logging
import re
import time
import uuid
from datetime import datetime, timezone


request_id_context = contextvars.ContextVar("airbee_request_id", default="-")
tenant_id_context = contextvars.ContextVar("airbee_tenant_id", default="-")
_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


def current_request_id() -> str:
    return request_id_context.get()


def bind_tenant(tenant_id: str | None) -> None:
    tenant_id_context.set(str(tenant_id or "-"))


class JsonFormatter(logging.Formatter):
    """Emit one JSON object per line for CloudWatch Logs Insights."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(
                record.created,
                tz=timezone.utc,
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(
                record,
                "request_id",
                request_id_context.get(),
            ),
            "tenant_id": getattr(
                record,
                "tenant_id",
                tenant_id_context.get(),
            ),
        }
        for field in (
            "method",
            "path",
            "status_code",
            "duration_ms",
            "error_code",
            "entity_type",
            "entity_id",
        ):
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


class RequestContextMiddleware:
    """Attach a correlation ID and log one completion event per request."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.logger = logging.getLogger("airbee.request")

    @staticmethod
    def _request_id(request) -> str:
        candidate = str(request.headers.get("X-Request-ID") or "").strip()
        return candidate if _VALID_REQUEST_ID.fullmatch(candidate) else str(uuid.uuid4())

    @staticmethod
    def _audit_successful_mutation(request, response, request_id: str) -> None:
        if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
            return
        if not 200 <= response.status_code < 300:
            return
        if response.headers.get("Idempotency-Replayed") == "true":
            return
        user = getattr(request, "user", None)
        tenant_id = getattr(user, "tenant_id", None)
        if not tenant_id:
            return

        segments = [part for part in request.path.strip("/").split("/") if part]
        if len(segments) < 2 or segments[0] not in {"api", "ai"}:
            return
        entity_type = segments[1][:100]
        action = {
            "POST": "create",
            "PUT": "update",
            "PATCH": "update",
            "DELETE": "delete",
        }[request.method]

        entity_id = None
        resolver_match = getattr(request, "resolver_match", None)
        if resolver_match:
            for key, value in resolver_match.kwargs.items():
                if key.endswith("_id"):
                    entity_id = value
                    break
        response_data = getattr(response, "data", None)
        if not entity_id and isinstance(response_data, dict):
            entity_id = response_data.get("id")
            if not entity_id:
                for value in response_data.values():
                    if isinstance(value, dict) and value.get("id"):
                        entity_id = value["id"]
                        break

        from api.views.audit_log import log_action

        log_action(
            tenant_id,
            action,
            entity_type,
            entity_id=entity_id,
            new_value={"request_id": request_id, "path": request.path},
            request=request,
        )

    def __call__(self, request):
        request_id = self._request_id(request)
        request.request_id = request_id
        request_token = request_id_context.set(request_id)
        tenant_token = tenant_id_context.set("-")
        started = time.perf_counter()
        response = None
        try:
            response = self.get_response(request)
            response["X-Request-ID"] = request_id
            self._audit_successful_mutation(request, response, request_id)
            return response
        finally:
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            self.logger.info(
                "request_completed",
                extra={
                    "method": request.method,
                    "path": request.path,
                    "status_code": getattr(response, "status_code", 500),
                    "duration_ms": duration_ms,
                },
            )
            tenant_id_context.reset(tenant_token)
            request_id_context.reset(request_token)
