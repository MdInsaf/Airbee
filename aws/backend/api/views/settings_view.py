import json
import os
import re
import uuid
from decimal import Decimal
from datetime import datetime, timezone

import dns.exception
import dns.resolver
from django.db import connection
from rest_framework.views import APIView
from rest_framework.response import Response

from api.domain_automation import (
    classify_amplify_domain_state,
    deprovision_amplify_custom_domain,
    format_domain_automation_error,
    get_amplify_settings,
    get_domain_automation_provider,
    sync_amplify_custom_domain,
)

_RESERVED_SUBDOMAINS = {
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


def _coerce_object(value):
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            return {}
    return {}


def _sanitize_subdomain(value):
    return re.sub(r"-{2,}", "-", re.sub(r"[^a-z0-9-]+", "-", str(value or "").strip().lower())).strip("-")


def _normalize_domain(value):
    raw = str(value or "").strip().lower()
    if not raw:
        return None
    raw = re.sub(r"^https?://", "", raw)
    raw = raw.rstrip("/").split("/")[0]
    return raw or None


def _get_platform_base_domain():
    return str(os.environ.get("PUBLIC_BASE_DOMAIN", "") or "").strip().lower() or None


def _build_primary_hostname(subdomain, domain=None, domain_status="verified"):
    normalized_domain = _normalize_domain(domain)
    if normalized_domain and str(domain_status or "").strip().lower() == "verified":
        return normalized_domain
    base_domain = _get_platform_base_domain()
    if subdomain and base_domain:
        return f"{subdomain}.{base_domain}"
    return subdomain or None


def _normalize_dns_name(value):
    return str(value or "").strip().lower().rstrip(".")


def _get_domain_verification_target():
    return _normalize_dns_name(os.environ.get("PUBLIC_CNAME_TARGET", ""))


def _resolve_cname_targets(domain):
    resolver = dns.resolver.Resolver()
    answers = resolver.resolve(domain, "CNAME")
    return [_normalize_dns_name(getattr(answer, "target", answer).to_text()) for answer in answers]


def _extract_platform_subdomain(hostname):
    normalized_host = _normalize_domain(hostname)
    base_domain = _get_platform_base_domain()
    if not normalized_host or not base_domain:
        return None
    suffix = f".{base_domain}"
    if normalized_host == base_domain or not normalized_host.endswith(suffix):
        return None
    return normalized_host[: -len(suffix)] or None


def _find_hostname_conflict(cur, hostname, tenant_id):
    normalized_host = _normalize_domain(hostname)
    if not normalized_host:
        return None

    platform_subdomain = _extract_platform_subdomain(normalized_host)
    cur.execute(
        """
        SELECT id, name, slug, subdomain, domain, primary_hostname
        FROM tenants
        WHERE id != %s
          AND (
            lower(COALESCE(domain, '')) = lower(%s)
            OR lower(COALESCE(primary_hostname, '')) = lower(%s)
            OR (%s IS NOT NULL AND lower(COALESCE(subdomain, '')) = lower(%s))
          )
        LIMIT 1
        """,
        [tenant_id, normalized_host, normalized_host, platform_subdomain, platform_subdomain],
    )
    row = cur.fetchone()
    if not row:
        return None
    columns = [column[0] for column in cur.description]
    return _serialize(row, columns)


def _build_domain_setup(tenant):
    provider = get_domain_automation_provider()
    base_domain = _get_platform_base_domain()
    cname_target = _get_domain_verification_target() or None
    subdomain = tenant.get("subdomain")
    custom_domain = tenant.get("domain")
    domain_config = _coerce_object(tenant.get("domain_config"))
    subdomain_fqdn = f"{subdomain}.{base_domain}" if subdomain and base_domain else None
    platform_booking_url = f"https://{subdomain_fqdn}" if subdomain_fqdn else None
    custom_domain_url = f"https://{custom_domain}" if custom_domain else None
    verified = (tenant.get("domain_status") or "").lower() == "verified"
    preview_url = custom_domain_url if verified and custom_domain_url else platform_booking_url

    status = tenant.get("domain_status") or "none"
    dns_records = []
    verification = None
    provider_status = None
    provider_update_status = None

    if provider == "amplify" and custom_domain:
        dns_records = domain_config.get("dns_records") or []
        provider_status = domain_config.get("association_status")
        provider_update_status = domain_config.get("update_status")
        if status == "verified":
            status_message = "Amplify has connected this custom domain and it is ready to serve traffic."
        elif status == "failed":
            status_message = tenant.get("domain_last_error") or "Amplify failed to provision the custom domain."
        elif dns_records:
            status_message = tenant.get("domain_last_error") or "Create the DNS records below, then sync the custom domain again."
        else:
            status_message = tenant.get("domain_last_error") or "Save a custom domain and sync it to generate Amplify DNS records."
    else:
        if status == "verified":
            status_message = "Custom domain verified and ready to use."
        elif status == "failed":
            status_message = tenant.get("domain_last_error") or "Verification failed. Check the DNS record and try again."
        elif status == "pending":
            status_message = "Point your custom domain CNAME record to the target below, then verify it."
        else:
            status_message = "Using platform subdomain until a custom domain is connected."

        if custom_domain and cname_target:
            verification = {
                "record_type": "CNAME",
                "record_name": custom_domain,
                "record_value": cname_target,
            }
            dns_records = [verification]

    return {
        "provider": provider,
        "platform_base_domain": base_domain,
        "subdomain_fqdn": subdomain_fqdn,
        "platform_booking_url": platform_booking_url,
        "custom_domain_url": custom_domain_url,
        "preview_url": preview_url,
        "cname_target": cname_target,
        "status_message": status_message,
        "verification": verification,
        "dns_records": dns_records,
        "provider_status": provider_status,
        "provider_update_status": provider_update_status,
        "provider_branch": domain_config.get("branch"),
        "provider_region": domain_config.get("region"),
    }


def _format_deprovision_message(result):
    if not isinstance(result, dict):
        return None
    action = str(result.get("action") or "").strip().lower()
    if action == "deleted":
        return f"Removed the previous custom domain {result.get('full_domain')} from Amplify."
    if action == "updated":
        return f"Removed the previous custom domain {result.get('full_domain')} and kept the remaining Amplify domain mappings."
    if action == "noop":
        return result.get("message")
    return None


def _validate_subdomain(value):
    subdomain = _sanitize_subdomain(value)
    if not subdomain:
        return None, "Subdomain is required"
    if len(subdomain) < 3 or len(subdomain) > 63:
        return None, "Subdomain must be between 3 and 63 characters"
    if subdomain in _RESERVED_SUBDOMAINS:
        return None, "That subdomain is reserved"
    if not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?", subdomain):
        return None, "Subdomain can only use lowercase letters, numbers, and hyphens"
    return subdomain, None


def _validate_domain(value):
    domain = _normalize_domain(value)
    if domain is None:
        return None, None
    if len(domain) > 253 or not re.fullmatch(r"[a-z0-9.-]+\.[a-z]{2,}", domain):
        return None, "Custom domain must look like stay.example.com"
    return domain, None


def _load_tenant(cur, tenant_id):
    cur.execute(
        """
        SELECT id, name, slug, subdomain, domain, primary_hostname, booking_site_enabled,
               domain_status, domain_verified_at, domain_last_checked_at, domain_last_error,
               settings, booking_theme, domain_config,
               gst_enabled, gst_percentage, gst_number, service_charge_enabled,
               service_charge_percentage, email_settings, contact_email, contact_phone,
               address, currency, timezone, logo_url, created_at, updated_at
        FROM tenants
        WHERE id = %s
        """,
        [tenant_id],
    )
    tenant_row = cur.fetchone()
    tenant_cols = [c[0] for c in cur.description]
    tenant = _serialize(tenant_row, tenant_cols) if tenant_row else None
    if tenant:
        tenant["settings"] = _coerce_object(tenant.get("settings"))
        tenant["booking_theme"] = _coerce_object(tenant.get("booking_theme"))
        tenant["domain_config"] = _coerce_object(tenant.get("domain_config"))
        tenant["domain_setup"] = _build_domain_setup(tenant)
    return tenant


class SettingsView(APIView):
    def get(self, request):
        tenant_id = request.user.tenant_id
        user_sub = request.user.sub
        with connection.cursor() as cur:
            tenant = _load_tenant(cur, tenant_id)

            cur.execute(
                """
                SELECT id, tenant_id, full_name, phone, avatar_url, created_at, updated_at
                FROM profiles
                WHERE id = %s
                """,
                [user_sub],
            )
            profile_row = cur.fetchone()
            profile_cols = [c[0] for c in cur.description]

            cur.execute(
                """
                SELECT id, tenant_id, name, color, display_order, description, created_at, updated_at
                FROM room_categories
                WHERE tenant_id = %s
                ORDER BY display_order, name
                """,
                [tenant_id],
            )
            category_cols = [c[0] for c in cur.description]
            category_rows = [_serialize(r, category_cols) for r in cur.fetchall()]

        return Response(
            {
                "tenant": tenant,
                "profile": _serialize(profile_row, profile_cols) if profile_row else None,
                "room_categories": category_rows,
            }
        )

    def put(self, request):
        tenant_id = request.user.tenant_id
        d = request.data
        provider = get_domain_automation_provider()
        with connection.cursor() as cur:
            tenant = _load_tenant(cur, tenant_id)
            if not tenant:
                return Response({"error": "Tenant not found"}, status=404)

            current_domain = _normalize_domain(tenant.get("domain"))
            subdomain_input = d.get("subdomain", tenant.get("subdomain"))
            subdomain, subdomain_error = _validate_subdomain(subdomain_input)
            if subdomain_error:
                return Response({"error": subdomain_error}, status=400)

            domain_input = d.get("domain", tenant.get("domain"))
            domain, domain_error = _validate_domain(domain_input)
            if domain_error:
                return Response({"error": domain_error}, status=400)

            cur.execute(
                """
                SELECT 1
                FROM tenants
                WHERE lower(subdomain) = lower(%s) AND id != %s
                LIMIT 1
                """,
                [subdomain, tenant_id],
            )
            if cur.fetchone():
                return Response({"error": "That subdomain is already in use"}, status=409)

            if domain:
                cur.execute(
                    """
                    SELECT 1
                    FROM tenants
                    WHERE lower(domain) = lower(%s) AND id != %s
                    LIMIT 1
                    """,
                    [domain, tenant_id],
                )
                if cur.fetchone():
                    return Response({"error": "That custom domain is already in use"}, status=409)

            platform_hostname = _build_primary_hostname(subdomain, None, "none")
            hostname_conflict = _find_hostname_conflict(cur, platform_hostname, tenant_id)
            if hostname_conflict:
                return Response(
                    {
                        "error": "That subdomain conflicts with another property's active hostname",
                        "conflict": hostname_conflict,
                    },
                    status=409,
                )

            if domain:
                domain_conflict = _find_hostname_conflict(cur, domain, tenant_id)
                if domain_conflict:
                    return Response(
                        {
                            "error": "That custom domain conflicts with another property's hostname",
                            "conflict": domain_conflict,
                        },
                        status=409,
                    )

            existing_settings = _coerce_object(tenant.get("settings"))
            existing_booking_site = _coerce_object(existing_settings.get("booking_site"))
            incoming_booking_site = _coerce_object(d.get("booking_site"))
            booking_site = {**existing_booking_site, **incoming_booking_site}
            settings_payload = {**existing_settings, "booking_site": booking_site}

            existing_theme = _coerce_object(tenant.get("booking_theme"))
            incoming_theme = _coerce_object(d.get("booking_theme"))
            booking_theme = {**existing_theme, **incoming_theme}
            existing_domain_config = _coerce_object(tenant.get("domain_config"))

            booking_site_enabled = d.get("booking_site_enabled")
            if booking_site_enabled is None:
                booking_site_enabled = tenant.get("booking_site_enabled", True)
            else:
                booking_site_enabled = bool(booking_site_enabled)

            domain_changed = current_domain != domain
            deprovision_result = None
            if provider == "amplify" and domain_changed and current_domain:
                try:
                    deprovision_result = deprovision_amplify_custom_domain(current_domain)
                except Exception as exc:
                    return Response(
                        {
                            "error": f"Could not remove the previous custom domain from Amplify: {format_domain_automation_error(exc)}",
                            "tenant": tenant,
                        },
                        status=502,
                    )

            if domain:
                domain_status = "pending" if domain_changed else (tenant.get("domain_status") or "pending")
                domain_verified_at = None if domain_changed else tenant.get("domain_verified_at")
                domain_last_checked_at = None if domain_changed else tenant.get("domain_last_checked_at")
                if domain_changed and provider == "amplify":
                    domain_last_error = "Custom domain saved. Sync it to generate Amplify DNS records."
                else:
                    domain_last_error = None if domain_changed else tenant.get("domain_last_error")
                domain_config = {} if domain_changed else existing_domain_config
            else:
                domain_status = "none"
                domain_verified_at = None
                domain_last_checked_at = None
                domain_last_error = None
                domain_config = {}

            cur.execute(
                """
                UPDATE tenants SET
                    name = COALESCE(%s, name),
                    subdomain = %s,
                    domain = %s,
                    primary_hostname = %s,
                    booking_site_enabled = %s,
                    domain_status = %s,
                    domain_verified_at = %s,
                    domain_last_checked_at = %s,
                    domain_last_error = %s,
                    domain_config = %s::jsonb,
                    settings = %s::jsonb,
                    booking_theme = %s::jsonb,
                    logo_url = COALESCE(%s, logo_url),
                    contact_email = COALESCE(%s, contact_email),
                    contact_phone = COALESCE(%s, contact_phone),
                    address = COALESCE(%s, address),
                    timezone = COALESCE(%s, timezone),
                    currency = COALESCE(%s, currency),
                    gst_enabled = COALESCE(%s, gst_enabled),
                    gst_percentage = COALESCE(%s, gst_percentage),
                    gst_number = COALESCE(%s, gst_number),
                    service_charge_enabled = COALESCE(%s, service_charge_enabled),
                    service_charge_percentage = COALESCE(%s, service_charge_percentage),
                    updated_at = NOW()
                WHERE id = %s
                """,
                [
                    d.get("name"),
                    subdomain,
                    domain,
                    _build_primary_hostname(subdomain, domain, domain_status),
                    booking_site_enabled,
                    domain_status,
                    domain_verified_at,
                    domain_last_checked_at,
                    domain_last_error,
                    json.dumps(domain_config),
                    json.dumps(settings_payload),
                    json.dumps(booking_theme),
                    d.get("logo_url"),
                    d.get("contact_email"),
                    d.get("contact_phone"),
                    d.get("address"),
                    d.get("timezone"),
                    d.get("currency"),
                    d.get("gst_enabled"),
                    d.get("gst_percentage"),
                    d.get("gst_number"),
                    d.get("service_charge_enabled"),
                    d.get("service_charge_percentage"),
                    tenant_id,
                ],
            )
            tenant = _load_tenant(cur, tenant_id)

        response_message = _format_deprovision_message(deprovision_result)
        if not response_message and provider == "amplify" and domain_changed and domain:
            response_message = "Previous custom domain removed. Sync the new custom domain to generate fresh Amplify DNS records."

        response_payload = {"success": True, "tenant": tenant}
        if response_message:
            response_payload["message"] = response_message
        return Response(response_payload)


class DomainVerificationView(APIView):
    def post(self, request):
        tenant_id = request.user.tenant_id
        provider = get_domain_automation_provider()
        expected_target = _get_domain_verification_target()
        amplify_settings = get_amplify_settings()
        if provider == "manual":
            return Response(
                {"error": "Custom domain automation is not configured on the server"},
                status=500,
            )
        if provider == "cname" and not expected_target:
            return Response(
                {"error": "Custom domain verification is not configured on the server"},
                status=500,
            )

        with connection.cursor() as cur:
            tenant = _load_tenant(cur, tenant_id)
            if not tenant:
                return Response({"error": "Tenant not found"}, status=404)

            domain = _normalize_domain(tenant.get("domain"))
            if not domain:
                return Response({"error": "No custom domain is configured for this property"}, status=400)

            hostname_conflict = _find_hostname_conflict(cur, domain, tenant_id)
            if hostname_conflict:
                return Response(
                    {
                        "error": "This custom domain conflicts with another property's hostname",
                        "conflict": hostname_conflict,
                        "tenant": tenant,
                    },
                    status=409,
                )

            checked_at = datetime.now(timezone.utc)
            if provider == "amplify":
                try:
                    domain_config = sync_amplify_custom_domain(domain)
                    domain_status, error_message = classify_amplify_domain_state(domain_config)
                except Exception as exc:
                    domain_config = {
                        "provider": "amplify",
                        "app_id": amplify_settings["app_id"],
                        "region": amplify_settings["region"],
                        "branch": amplify_settings["branch"],
                        "full_domain": domain,
                    }
                    domain_status = "failed"
                    error_message = format_domain_automation_error(exc)

                verified = domain_status == "verified"
                cur.execute(
                    """
                    UPDATE tenants
                    SET domain_status = %s,
                        domain_verified_at = %s,
                        domain_last_checked_at = %s,
                        domain_last_error = %s,
                        domain_config = %s::jsonb,
                        primary_hostname = %s,
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    [
                        domain_status,
                        checked_at if verified else None,
                        checked_at,
                        None if verified else error_message,
                        json.dumps(domain_config),
                        domain if verified else _build_primary_hostname(tenant.get("subdomain"), None, "none"),
                        tenant_id,
                    ],
                )
            else:
                try:
                    resolved_targets = _resolve_cname_targets(domain)
                except dns.resolver.NXDOMAIN:
                    resolved_targets = []
                    error_message = "DNS record not found for this custom domain"
                except (dns.resolver.NoAnswer, dns.resolver.NoNameservers, dns.exception.Timeout) as exc:
                    resolved_targets = []
                    error_message = f"Could not verify DNS yet: {exc}"
                except Exception as exc:
                    resolved_targets = []
                    error_message = f"Verification failed: {exc}"
                else:
                    error_message = None

                verified = expected_target in resolved_targets
                domain_config = _coerce_object(tenant.get("domain_config"))
                if verified:
                    cur.execute(
                        """
                        UPDATE tenants
                        SET domain_status = 'verified',
                            domain_verified_at = %s,
                            domain_last_checked_at = %s,
                            domain_last_error = NULL,
                            domain_config = %s::jsonb,
                            primary_hostname = %s,
                            updated_at = NOW()
                        WHERE id = %s
                        """,
                        [checked_at, checked_at, json.dumps(domain_config), domain, tenant_id],
                    )
                else:
                    cur.execute(
                        """
                        UPDATE tenants
                        SET domain_status = 'failed',
                            domain_verified_at = NULL,
                            domain_last_checked_at = %s,
                            domain_last_error = %s,
                            domain_config = %s::jsonb,
                            primary_hostname = %s,
                            updated_at = NOW()
                        WHERE id = %s
                        """,
                        [
                            checked_at,
                            error_message
                            or f"Expected CNAME target {expected_target}, got {', '.join(resolved_targets) or 'no CNAME record'}",
                            json.dumps(domain_config),
                            _build_primary_hostname(tenant.get("subdomain"), None, "none"),
                            tenant_id,
                        ],
                    )

            tenant = _load_tenant(cur, tenant_id)

        if verified:
            success_message = (
                "Custom domain synced successfully with Amplify"
                if provider == "amplify"
                else "Custom domain verified successfully"
            )
            return Response(
                {
                    "success": True,
                    "message": success_message,
                    "tenant": tenant,
                }
            )

        return Response(
            {
                "success": False,
                "message": tenant.get("domain_last_error") or "Custom domain is not verified yet",
                "tenant": tenant,
            },
            status=409,
        )


class RoomCategoriesView(APIView):
    def get(self, request):
        tenant_id = request.user.tenant_id
        with connection.cursor() as cur:
            cur.execute(
                """
                SELECT id, tenant_id, name, color, display_order, description, created_at, updated_at
                FROM room_categories
                WHERE tenant_id = %s
                ORDER BY display_order, name
                """,
                [tenant_id],
            )
            cols = [c[0] for c in cur.description]
            rows = [_serialize(r, cols) for r in cur.fetchall()]
        return Response(rows)
