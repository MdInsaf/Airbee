"""Stable API exceptions and a sanitized DRF exception handler."""

from __future__ import annotations

import logging

from rest_framework import status
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from api.observability import current_request_id


logger = logging.getLogger("airbee.api")


class AirbeeAPIException(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "AIRBEE_ERROR"
    default_detail = "The request could not be completed"

    def __init__(self, message=None, *, code=None, details=None):
        super().__init__(detail=message or self.default_detail, code=code or self.default_code)
        self.airbee_code = code or self.default_code
        self.details = details or {}


class ResourceNotFoundError(AirbeeAPIException):
    status_code = status.HTTP_404_NOT_FOUND
    default_code = "RESOURCE_NOT_FOUND"


class ConflictError(AirbeeAPIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "CONFLICT"


def safe_error_response(
    message: str,
    *,
    code: str = "INVALID_REQUEST",
    status_code: int = status.HTTP_400_BAD_REQUEST,
    exc: Exception | None = None,
) -> Response:
    """Log internal details while returning a stable, non-sensitive error."""
    if exc is not None:
        logger.warning(
            "handled_api_error",
            exc_info=(type(exc), exc, exc.__traceback__),
            extra={"status_code": status_code, "error_code": code},
        )
    return Response(
        {
            "code": code,
            "message": message,
            "request_id": current_request_id(),
        },
        status=status_code,
    )


def airbee_exception_handler(exc, context):
    request_id = current_request_id()
    response = drf_exception_handler(exc, context)

    if response is None:
        logger.exception(
            "unhandled_api_exception",
            exc_info=(type(exc), exc, exc.__traceback__),
            extra={"error_code": "INTERNAL_ERROR"},
        )
        return Response(
            {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
                "request_id": request_id,
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    if isinstance(exc, AirbeeAPIException):
        code = exc.airbee_code
        message = str(exc.detail)
        details = exc.details
    elif isinstance(exc, ValidationError):
        code = "VALIDATION_ERROR"
        message = "Request validation failed"
        details = response.data
    else:
        code = getattr(exc, "default_code", None) or "REQUEST_ERROR"
        code = str(code).upper()
        detail = response.data.get("detail") if isinstance(response.data, dict) else None
        message = str(detail or "The request could not be completed")
        details = {}

    response.data = {
        "code": code,
        "message": message,
        "details": details,
        "request_id": request_id,
    }
    if response.status_code >= 500:
        logger.error(
            "api_exception",
            extra={"status_code": response.status_code, "error_code": code},
        )
    return response
