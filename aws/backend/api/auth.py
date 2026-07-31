import os
import time
import jwt
import requests
from django.conf import settings
from django.db import connection
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from api.observability import bind_tenant

# Local dev tenant — matches seed_local.sql
_LOCAL_TENANT_ID = "00000000-0000-0000-0000-000000000001"

_jwks_cache = None
_jwks_cached_at = 0.0
_JWKS_TTL_SECONDS = 60 * 60


def _get_user_role(user_id, tenant_id):
    """Get user's role from database, default to guest."""
    try:
        with connection.cursor() as cur:
            cur.execute(
                "SELECT role FROM user_roles WHERE user_id = %s AND tenant_id = %s LIMIT 1",
                [user_id, tenant_id],
            )
            row = cur.fetchone()
            return row[0] if row else "guest"
    except Exception:
        return "guest"


def _get_jwks(force_refresh=False):
    global _jwks_cache, _jwks_cached_at
    cache_expired = time.monotonic() - _jwks_cached_at >= _JWKS_TTL_SECONDS
    if force_refresh or _jwks_cache is None or cache_expired:
        if not settings.COGNITO_USER_POOL_ID:
            raise AuthenticationFailed("Cognito user pool is not configured")
        url = (
            f"https://cognito-idp.{settings.COGNITO_REGION}.amazonaws.com"
            f"/{settings.COGNITO_USER_POOL_ID}/.well-known/jwks.json"
        )
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        _jwks_cache = resp.json()
        _jwks_cached_at = time.monotonic()
    return _jwks_cache


class CognitoUser:
    def __init__(self, sub, tenant_id, email, role="guest"):
        self.sub = sub
        self.pk = sub
        self.id = sub
        self.tenant_id = tenant_id
        self.email = email
        self.role = role
        self.is_authenticated = True


class CognitoAuthentication(BaseAuthentication):
    def authenticate(self, request):
        # ── Local dev bypass ────────────────────────────────────
        if getattr(settings, "LOCAL_DEV", False):
            bind_tenant(_LOCAL_TENANT_ID)
            return (
                CognitoUser(
                    sub="local-dev-user",
                    tenant_id=_LOCAL_TENANT_ID,
                    email="dev@airbee.local",
                    role="owner",  # Dev user is always owner
                ),
                None,
            )
        # ────────────────────────────────────────────────────────

        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        if not auth_header.startswith("Bearer "):
            return None

        token = auth_header[7:]
        try:
            if not settings.COGNITO_CLIENT_ID:
                raise AuthenticationFailed("Cognito client is not configured")

            unverified_header = jwt.get_unverified_header(token)
            if unverified_header.get("alg") != "RS256":
                raise AuthenticationFailed("Unsupported token signing algorithm")
            kid = unverified_header["kid"]

            jwks = _get_jwks()
            key_data = next((k for k in jwks["keys"] if k["kid"] == kid), None)
            if not key_data:
                jwks = _get_jwks(force_refresh=True)
                key_data = next((k for k in jwks["keys"] if k["kid"] == kid), None)
                if not key_data:
                    raise AuthenticationFailed("Token key not found in JWKS")

            public_key = jwt.algorithms.RSAAlgorithm.from_jwk(key_data)
            issuer = (
                f"https://cognito-idp.{settings.COGNITO_REGION}.amazonaws.com"
                f"/{settings.COGNITO_USER_POOL_ID}"
            )
            payload = jwt.decode(
                token,
                public_key,
                algorithms=["RS256"],
                audience=settings.COGNITO_CLIENT_ID,
                issuer=issuer,
                options={
                    "require": ["exp", "iss", "sub", "token_use"],
                    "verify_aud": True,
                },
            )

            if payload.get("token_use") != "id":
                raise AuthenticationFailed("Only Cognito ID tokens are accepted")

            tenant_id = payload.get("custom:tenant_id", "")
            if not tenant_id:
                raise AuthenticationFailed("custom:tenant_id claim missing — signup not completed")

            bind_tenant(tenant_id)

            # Load user's role from database
            role = _get_user_role(payload["sub"], tenant_id)

            return (
                CognitoUser(
                    sub=payload["sub"],
                    tenant_id=tenant_id,
                    email=payload.get("email", ""),
                    role=role,
                ),
                token,
            )
        except AuthenticationFailed:
            raise
        except Exception as exc:
            raise AuthenticationFailed(f"Invalid token: {exc}")
