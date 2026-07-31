"""Idempotent Cognito PostConfirmation tenant provisioning."""

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid

import boto3
import psycopg2


DB_CONFIG = {
    "host": os.environ["DB_HOST"],
    "port": int(os.environ.get("DB_PORT", 5432)),
    "dbname": os.environ.get("DB_NAME", "airbee"),
    "user": os.environ["DB_USER"],
    "password": os.environ["DB_PASSWORD"],
    "sslmode": os.environ.get("DB_SSLMODE", "require"),
    "connect_timeout": 10,
}

RESERVED_SUBDOMAINS = {
    "admin",
    "api",
    "app",
    "auth",
    "book",
    "booking",
    "dashboard",
    "docs",
    "help",
    "mail",
    "root",
    "settings",
    "support",
    "www",
}


def _sanitize_label(value: str, fallback: str = "property") -> str:
    label = re.sub(r"-{2,}", "-", re.sub(r"[^a-z0-9-]+", "-", str(value or "").lower()))
    return label.strip("-")[:63] or fallback


def _stable_suffix(cognito_sub: str, length: int = 10) -> str:
    compact = re.sub(r"[^a-z0-9]", "", str(cognito_sub or "").lower())
    if len(compact) >= length:
        return compact[:length]
    return hashlib.sha256(str(cognito_sub).encode("utf-8")).hexdigest()[:length]


def _primary_hostname(subdomain: str) -> str:
    base_domain = os.environ.get("PUBLIC_BASE_DOMAIN", "").strip().lower().strip(".")
    return f"{subdomain}.{base_domain}" if base_domain else subdomain


def _candidate_identity(full_name: str, cognito_sub: str, attempt: int) -> tuple[str, str]:
    base = _sanitize_label(full_name)
    if base in RESERVED_SUBDOMAINS:
        base = f"{base}-hotel"
    suffix_seed = _stable_suffix(cognito_sub)
    suffix = suffix_seed if attempt == 0 else f"{suffix_seed}-{attempt}"
    max_base_length = max(1, 63 - len(suffix) - 1)
    subdomain = f"{base[:max_base_length].rstrip('-')}-{suffix}"
    slug = subdomain
    return slug, subdomain


def _find_or_create_tenant(cur, cognito_sub: str, full_name: str, email: str) -> str:
    cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", [f"airbee-provision:{cognito_sub}"])

    cur.execute(
        """
        SELECT p.tenant_id
        FROM profiles p
        JOIN tenants t ON t.id = p.tenant_id
        WHERE p.id = %s
        FOR UPDATE OF p
        """,
        [cognito_sub],
    )
    row = cur.fetchone()
    if row:
        return str(row[0])

    tenant_id = str(uuid.uuid4())
    booking_site = {
        "hero_title": f"{full_name}'s Property",
        "hero_subtitle": "Search live availability and book directly.",
        "support_email": email,
        "support_phone": "",
        "cta_label": "Book your stay",
    }
    booking_theme = {
        "primary_color": "#f59e0b",
        "accent_color": "#111827",
        "surface_style": "warm",
    }

    for attempt in range(100):
        slug, subdomain = _candidate_identity(full_name, cognito_sub, attempt)
        hostname = _primary_hostname(subdomain)
        cur.execute(
            """
            SELECT 1
            FROM tenants
            WHERE lower(slug) = lower(%s)
               OR lower(COALESCE(subdomain, '')) = lower(%s)
               OR lower(COALESCE(primary_hostname, '')) = lower(%s)
            LIMIT 1
            """,
            [slug, subdomain, hostname],
        )
        if cur.fetchone():
            continue

        cur.execute("SAVEPOINT airbee_tenant_candidate")
        try:
            cur.execute(
                """
                INSERT INTO tenants (
                    id, name, slug, subdomain, primary_hostname,
                    booking_site_enabled, domain_status, settings, booking_theme,
                    contact_email, currency, timezone
                )
                VALUES (
                    %s, %s, %s, %s, %s,
                    true, 'none', %s::jsonb, %s::jsonb,
                    %s, 'INR', 'Asia/Kolkata'
                )
                """,
                [
                    tenant_id,
                    f"{full_name}'s Property",
                    slug,
                    subdomain,
                    hostname,
                    json.dumps({"booking_site": booking_site}),
                    json.dumps(booking_theme),
                    email or None,
                ],
            )
        except psycopg2.errors.UniqueViolation:
            cur.execute("ROLLBACK TO SAVEPOINT airbee_tenant_candidate")
            cur.execute("RELEASE SAVEPOINT airbee_tenant_candidate")
            continue
        cur.execute("RELEASE SAVEPOINT airbee_tenant_candidate")
        return tenant_id

    raise RuntimeError("Could not allocate a unique property slug")


def _ensure_tenant_defaults(cur, tenant_id: str, cognito_sub: str, full_name: str) -> None:
    cur.execute(
        """
        INSERT INTO profiles (id, tenant_id, full_name)
        VALUES (%s, %s, %s)
        ON CONFLICT (id) DO UPDATE
        SET tenant_id = EXCLUDED.tenant_id,
            full_name = EXCLUDED.full_name,
            updated_at = now()
        """,
        [cognito_sub, tenant_id, full_name],
    )
    cur.execute(
        """
        INSERT INTO user_roles (user_id, tenant_id, role)
        VALUES (%s, %s, 'owner')
        ON CONFLICT (user_id, tenant_id, role) DO NOTHING
        """,
        [cognito_sub, tenant_id],
    )

    defaults = [
        ("Standard", "#6B7280", 1),
        ("Deluxe", "#3B82F6", 2),
        ("Suite", "#8B5CF6", 3),
        ("Villa", "#10B981", 4),
    ]
    for name, color, display_order in defaults:
        cur.execute(
            """
            INSERT INTO room_categories (tenant_id, name, color, display_order)
            SELECT %s, %s, %s, %s
            WHERE NOT EXISTS (
                SELECT 1
                FROM room_categories
                WHERE tenant_id = %s AND lower(name) = lower(%s)
            )
            """,
            [tenant_id, name, color, display_order, tenant_id, name],
        )

    pages = [
        (
            "home",
            "Home",
            [{"type": "hero", "data": {"title": "Welcome", "subtitle": "Experience comfort"}}],
            True,
        ),
        (
            "about",
            "About Us",
            [{"type": "text", "data": {"content": "Tell your story here."}}],
            False,
        ),
    ]
    for slug, title, blocks, published in pages:
        cur.execute(
            """
            INSERT INTO pages (tenant_id, slug, title, content_blocks, is_published)
            VALUES (%s, %s, %s, %s::jsonb, %s)
            ON CONFLICT (tenant_id, slug) DO NOTHING
            """,
            [tenant_id, slug, title, json.dumps(blocks), published],
        )


def handler(event, context):
    if event.get("triggerSource") != "PostConfirmation_ConfirmSignUp":
        return event

    user_attributes = event.get("request", {}).get("userAttributes", {}) or {}
    cognito_sub = user_attributes["sub"]
    email = str(user_attributes.get("email") or "").strip().lower()
    full_name = str(user_attributes.get("name") or email.split("@")[0] or "Property Owner").strip()
    connection = psycopg2.connect(**DB_CONFIG)
    connection.autocommit = False
    try:
        with connection.cursor() as cur:
            tenant_id = _find_or_create_tenant(
                cur,
                cognito_sub,
                full_name,
                email,
            )
            _ensure_tenant_defaults(cur, tenant_id, cognito_sub, full_name)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    cognito_client = boto3.client(
        "cognito-idp",
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
    )
    cognito_client.admin_update_user_attributes(
        UserPoolId=event["userPoolId"],
        Username=event["userName"],
        UserAttributes=[{"Name": "custom:tenant_id", "Value": tenant_id}],
    )

    print(
        json.dumps(
            {
                "event": "tenant_provisioned",
                "tenant_id": tenant_id,
                "sub": cognito_sub,
            }
        )
    )
    return event
