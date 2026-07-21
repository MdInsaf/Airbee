"""API versioning support for backward compatibility during major changes."""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger("airbee.versioning")

# Current API version
CURRENT_VERSION = "v1"

# List of supported versions (oldest first)
SUPPORTED_VERSIONS = ["v1", "v2"]

# Deprecation mapping: {deprecated_version: (removal_date, recommended_version)}
DEPRECATION_SCHEDULE = {
    # "v1": ("2026-12-31", "v2"),  # Example: deprecate v1 on date
}


def parse_api_version(request) -> str:
    """Extract API version from request.

    Supports:
    1. Accept-Version header: Accept-Version: v2
    2. URL version: /api/v2/...
    3. Query parameter: ?version=v2
    4. Default: CURRENT_VERSION

    Returns the requested version if supported, otherwise CURRENT_VERSION.
    """
    # Try Accept-Version header first (preferred)
    version = request.headers.get("Accept-Version", "").strip().lower()
    if version and version in SUPPORTED_VERSIONS:
        logger.debug(f"API version from header: {version}")
        return version

    # Try X-API-Version header (alternative)
    version = request.headers.get("X-API-Version", "").strip().lower()
    if version and version in SUPPORTED_VERSIONS:
        logger.debug(f"API version from X-API-Version header: {version}")
        return version

    # Try query parameter
    version = request.GET.get("version", "").strip().lower()
    if version and version in SUPPORTED_VERSIONS:
        logger.debug(f"API version from query parameter: {version}")
        return version

    # Try to extract from URL (e.g., /api/v2/...)
    path_parts = request.path.strip("/").split("/")
    for i, part in enumerate(path_parts):
        if part == "api" and i + 1 < len(path_parts):
            version = path_parts[i + 1].lower()
            if version in SUPPORTED_VERSIONS:
                logger.debug(f"API version from URL path: {version}")
                return version

    # Default to current version
    logger.debug(f"API version defaulting to: {CURRENT_VERSION}")
    return CURRENT_VERSION


def is_deprecated(version: str) -> bool:
    """Check if a version is scheduled for deprecation."""
    return version in DEPRECATION_SCHEDULE


def get_deprecation_warning(version: str) -> Optional[dict]:
    """Get deprecation warning for a version."""
    if version not in DEPRECATION_SCHEDULE:
        return None

    removal_date, recommended_version = DEPRECATION_SCHEDULE[version]
    return {
        "code": "API_VERSION_DEPRECATED",
        "message": f"API version {version} is deprecated and will be removed on {removal_date}",
        "removal_date": removal_date,
        "recommended_version": recommended_version,
    }


class APIVersionMiddleware:
    """Attach API version to request and include deprecation warnings in responses."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Parse version from request
        request.api_version = parse_api_version(request)

        # Get response
        response = self.get_response(request)

        # Add version headers
        response["API-Version"] = request.api_version
        response["API-Supported-Versions"] = ", ".join(SUPPORTED_VERSIONS)

        # Add deprecation warning if applicable
        deprecation = get_deprecation_warning(request.api_version)
        if deprecation:
            response["Deprecation"] = "true"
            response["Sunset"] = DEPRECATION_SCHEDULE[request.api_version][0]
            logger.warning(
                "deprecated_api_version_used",
                extra={
                    "version": request.api_version,
                    "removal_date": deprecation["removal_date"],
                },
            )
            # Optionally include warning in response body (for APIs that support it)
            if hasattr(response, "data") and isinstance(response.data, dict):
                if "deprecation_warning" not in response.data:
                    response.data["deprecation_warning"] = deprecation

        return response
