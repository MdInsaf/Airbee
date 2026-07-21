"""Signed, time-limited guest access tokens for booking self-service."""

from __future__ import annotations

import os
from urllib.parse import quote

from django.core import signing


TOKEN_SALT = "airbee.guest-booking-access.v1"
DEFAULT_MAX_AGE_SECONDS = 60 * 60 * 24 * 30


class GuestAccessError(ValueError):
    pass


def issue_guest_access_token(booking_id: str, tenant_id: str, email: str) -> str:
    normalized_email = str(email or "").strip().lower()
    if not booking_id or not tenant_id or not normalized_email:
        raise GuestAccessError("Booking access token requires booking, tenant, and email")
    return signing.dumps(
        {
            "v": 1,
            "booking_id": str(booking_id),
            "tenant_id": str(tenant_id),
            "email": normalized_email,
        },
        salt=TOKEN_SALT,
        compress=True,
    )


def read_guest_access_token(token: str) -> dict[str, str]:
    if not token:
        raise GuestAccessError("Booking access token is required")
    try:
        max_age = int(
            os.environ.get(
                "GUEST_ACCESS_TOKEN_MAX_AGE_SECONDS",
                str(DEFAULT_MAX_AGE_SECONDS),
            )
        )
        payload = signing.loads(token, salt=TOKEN_SALT, max_age=max_age)
    except signing.SignatureExpired as exc:
        raise GuestAccessError("Booking access link has expired") from exc
    except signing.BadSignature as exc:
        raise GuestAccessError("Booking access link is invalid") from exc

    if not isinstance(payload, dict) or payload.get("v") != 1:
        raise GuestAccessError("Booking access link is invalid")

    required = ("booking_id", "tenant_id", "email")
    if any(not payload.get(key) for key in required):
        raise GuestAccessError("Booking access link is invalid")
    return {key: str(payload[key]) for key in required}


def build_guest_portal_url(property_data: dict, token: str) -> str:
    configured_base = os.environ.get("GUEST_PORTAL_BASE_URL", "").strip().rstrip("/")
    if configured_base:
        base = configured_base
    else:
        hostname = str(property_data.get("primary_hostname") or "").strip()
        if not hostname:
            return ""
        base = f"https://{hostname}"
    return f"{base}/my-booking?token={quote(token, safe='')}"
