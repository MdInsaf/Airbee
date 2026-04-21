import os
import re
from datetime import datetime, timezone

import boto3
from botocore.exceptions import BotoCoreError, ClientError
import tldextract

_DNS_RECORD_PATTERN = re.compile(r"^(?P<name>\S+)\s+(?P<type>[A-Za-z]+)\s+(?P<value>.+)$")
_TLD_EXTRACTOR = tldextract.TLDExtract(suffix_list_urls=None)


def _normalize_domain(value):
    raw = str(value or "").strip().lower()
    if not raw:
        return None
    raw = re.sub(r"^https?://", "", raw)
    raw = raw.rstrip("/").split("/")[0]
    return raw or None


def get_domain_automation_provider():
    if str(os.environ.get("AMPLIFY_APP_ID", "") or "").strip():
        return "amplify"
    if str(os.environ.get("PUBLIC_CNAME_TARGET", "") or "").strip():
        return "cname"
    return "manual"


def get_amplify_settings():
    app_id = str(os.environ.get("AMPLIFY_APP_ID", "") or "").strip()
    region = str(os.environ.get("AMPLIFY_REGION", "") or os.environ.get("AWS_REGION", "us-east-1")).strip()
    branch = str(os.environ.get("AMPLIFY_BRANCH", "") or "main").strip()
    return {
        "app_id": app_id or None,
        "region": region or "us-east-1",
        "branch": branch or "main",
        "enabled": bool(app_id),
    }


def split_domain_for_amplify(custom_domain):
    normalized = _normalize_domain(custom_domain)
    if not normalized:
        return None, None

    extracted = _TLD_EXTRACTOR(normalized)
    if not extracted.domain or not extracted.suffix:
        return None, None

    root_domain = f"{extracted.domain}.{extracted.suffix}".lower()
    prefix = (extracted.subdomain or "").strip().lower()
    return root_domain, prefix


def parse_dns_record(label, raw_record):
    raw_value = str(raw_record or "").strip()
    if not raw_value:
        return None

    match = _DNS_RECORD_PATTERN.match(raw_value)
    if match:
        return {
            "label": label,
            "record_name": match.group("name"),
            "record_type": match.group("type").upper(),
            "record_value": match.group("value"),
            "raw": raw_value,
        }

    return {
        "label": label,
        "record_name": None,
        "record_type": None,
        "record_value": raw_value,
        "raw": raw_value,
    }


def _dedupe_dns_records(records):
    deduped = []
    seen = set()
    for record in records:
        if not record:
            continue
        key = (
            record.get("record_name"),
            record.get("record_type"),
            record.get("record_value"),
            record.get("raw"),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(record)
    return deduped


def _is_not_found_error(error):
    return isinstance(error, ClientError) and error.response.get("Error", {}).get("Code") == "NotFoundException"


def _amplify_client(region):
    return boto3.client("amplify", region_name=region)


def _load_domain_association(client, app_id, root_domain):
    try:
        response = client.get_domain_association(appId=app_id, domainName=root_domain)
    except ClientError as exc:
        if _is_not_found_error(exc):
            return None
        raise
    return response.get("domainAssociation")


def _merge_subdomain_settings(existing_settings, prefix, branch):
    desired_prefix = str(prefix or "").strip().lower()
    merged = []
    seen = False

    for item in existing_settings or []:
        raw_item = (item or {}).get("subDomainSetting") or item or {}
        existing_prefix = str(raw_item.get("prefix") or "").strip().lower()
        branch_name = str(raw_item.get("branchName") or branch).strip() or branch
        if existing_prefix == desired_prefix:
            merged.append({"prefix": desired_prefix, "branchName": branch})
            seen = True
        elif existing_prefix:
            merged.append({"prefix": existing_prefix, "branchName": branch_name})
        else:
            merged.append({"prefix": "", "branchName": branch_name})

    if not seen:
        merged.append({"prefix": desired_prefix, "branchName": branch})

    return merged


def _normalize_subdomain_settings(existing_settings, default_branch):
    normalized = []
    for item in existing_settings or []:
        raw_item = (item or {}).get("subDomainSetting") or item or {}
        prefix = str(raw_item.get("prefix") or "").strip().lower()
        branch_name = str(raw_item.get("branchName") or default_branch).strip() or default_branch
        normalized.append({"prefix": prefix, "branchName": branch_name})
    return normalized


def _upsert_domain_association(client, app_id, root_domain, prefix, branch):
    existing = _load_domain_association(client, app_id, root_domain)
    if not existing:
        response = client.create_domain_association(
            appId=app_id,
            domainName=root_domain,
            subDomainSettings=[{"prefix": prefix, "branchName": branch}],
            certificateSettings={"type": "AMPLIFY_MANAGED"},
        )
        return response.get("domainAssociation")

    merged_settings = _merge_subdomain_settings(existing.get("subDomains", []), prefix, branch)
    current_settings = _normalize_subdomain_settings(existing.get("subDomains", []), branch)

    if merged_settings != current_settings:
        response = client.update_domain_association(
            appId=app_id,
            domainName=root_domain,
            subDomainSettings=merged_settings,
        )
        return response.get("domainAssociation")

    return existing


def _build_amplify_dns_records(association, prefix):
    target_subdomain = None
    desired_prefix = str(prefix or "").strip().lower()
    for subdomain in association.get("subDomains", []):
        subdomain_prefix = str(((subdomain or {}).get("subDomainSetting") or {}).get("prefix") or "").strip().lower()
        if subdomain_prefix == desired_prefix:
            target_subdomain = subdomain
            break

    dns_records = _dedupe_dns_records(
        [
            parse_dns_record(
                "Certificate validation",
                association.get("certificateVerificationDNSRecord")
                or (association.get("certificate") or {}).get("certificateVerificationDNSRecord"),
            ),
            parse_dns_record(
                "Application routing",
                (target_subdomain or {}).get("dnsRecord"),
            ),
        ]
    )

    return target_subdomain, dns_records


def _remove_subdomain_setting(existing_settings, prefix, default_branch):
    desired_prefix = str(prefix or "").strip().lower()
    remaining = []
    removed = False

    for item in _normalize_subdomain_settings(existing_settings, default_branch):
        if item["prefix"] == desired_prefix:
            removed = True
            continue
        remaining.append(item)

    return remaining, removed


def sync_amplify_custom_domain(custom_domain):
    settings = get_amplify_settings()
    if not settings["enabled"]:
        raise ValueError("AMPLIFY_APP_ID is not configured")

    normalized_domain = _normalize_domain(custom_domain)
    root_domain, prefix = split_domain_for_amplify(normalized_domain)
    if not root_domain:
        raise ValueError("Custom domain must include a valid registrable domain")

    client = _amplify_client(settings["region"])
    association = _upsert_domain_association(
        client,
        settings["app_id"],
        root_domain,
        prefix,
        settings["branch"],
    )
    target_subdomain, dns_records = _build_amplify_dns_records(association or {}, prefix)

    return {
        "provider": "amplify",
        "app_id": settings["app_id"],
        "region": settings["region"],
        "branch": settings["branch"],
        "root_domain": root_domain,
        "prefix": prefix,
        "full_domain": normalized_domain,
        "association_arn": (association or {}).get("domainAssociationArn"),
        "association_status": (association or {}).get("domainStatus"),
        "update_status": (association or {}).get("updateStatus"),
        "status_reason": (association or {}).get("statusReason"),
        "certificate_verification_dns_record": (association or {}).get("certificateVerificationDNSRecord")
        or ((association or {}).get("certificate") or {}).get("certificateVerificationDNSRecord"),
        "target_dns_record": (target_subdomain or {}).get("dnsRecord"),
        "subdomain_verified": bool((target_subdomain or {}).get("verified")),
        "dns_records": dns_records,
        "last_synced_at": datetime.now(timezone.utc).isoformat(),
    }


def deprovision_amplify_custom_domain(custom_domain):
    settings = get_amplify_settings()
    if not settings["enabled"]:
        raise ValueError("AMPLIFY_APP_ID is not configured")

    normalized_domain = _normalize_domain(custom_domain)
    root_domain, prefix = split_domain_for_amplify(normalized_domain)
    if not root_domain:
        raise ValueError("Custom domain must include a valid registrable domain")

    client = _amplify_client(settings["region"])
    association = _load_domain_association(client, settings["app_id"], root_domain)
    if not association:
        return {
            "provider": "amplify",
            "app_id": settings["app_id"],
            "region": settings["region"],
            "branch": settings["branch"],
            "root_domain": root_domain,
            "prefix": prefix,
            "full_domain": normalized_domain,
            "action": "noop",
            "message": "No Amplify domain association existed for this custom domain.",
            "last_synced_at": datetime.now(timezone.utc).isoformat(),
        }

    remaining_settings, removed = _remove_subdomain_setting(
        association.get("subDomains", []),
        prefix,
        settings["branch"],
    )

    if not removed:
        return {
            "provider": "amplify",
            "app_id": settings["app_id"],
            "region": settings["region"],
            "branch": settings["branch"],
            "root_domain": root_domain,
            "prefix": prefix,
            "full_domain": normalized_domain,
            "action": "noop",
            "message": "The Amplify domain association did not include this custom domain.",
            "last_synced_at": datetime.now(timezone.utc).isoformat(),
        }

    if remaining_settings:
        response = client.update_domain_association(
            appId=settings["app_id"],
            domainName=root_domain,
            subDomainSettings=remaining_settings,
        )
        updated = response.get("domainAssociation") or {}
        return {
            "provider": "amplify",
            "app_id": settings["app_id"],
            "region": settings["region"],
            "branch": settings["branch"],
            "root_domain": root_domain,
            "prefix": prefix,
            "full_domain": normalized_domain,
            "action": "updated",
            "association_status": updated.get("domainStatus"),
            "update_status": updated.get("updateStatus"),
            "status_reason": updated.get("statusReason"),
            "remaining_subdomains": _normalize_subdomain_settings(updated.get("subDomains", []), settings["branch"]),
            "last_synced_at": datetime.now(timezone.utc).isoformat(),
        }

    response = client.delete_domain_association(
        appId=settings["app_id"],
        domainName=root_domain,
    )
    deleted = response.get("domainAssociation") or {}
    return {
        "provider": "amplify",
        "app_id": settings["app_id"],
        "region": settings["region"],
        "branch": settings["branch"],
        "root_domain": root_domain,
        "prefix": prefix,
        "full_domain": normalized_domain,
        "action": "deleted",
        "association_status": deleted.get("domainStatus"),
        "update_status": deleted.get("updateStatus"),
        "status_reason": deleted.get("statusReason"),
        "last_synced_at": datetime.now(timezone.utc).isoformat(),
    }


def classify_amplify_domain_state(config):
    association_status = str((config or {}).get("association_status") or "").strip().upper()
    update_status = str((config or {}).get("update_status") or "").strip().upper()
    reason = (config or {}).get("status_reason")
    verified = bool((config or {}).get("subdomain_verified")) and association_status == "AVAILABLE"

    if verified:
        return "verified", None

    if "FAIL" in association_status or "FAIL" in update_status or "ERROR" in association_status:
        return "failed", reason or "Amplify failed to provision the custom domain"

    pending_reason = reason or "Add the DNS records below and wait for Amplify to verify and deploy the custom domain."
    return "pending", pending_reason


def format_domain_automation_error(exc):
    if isinstance(exc, ValueError):
        return str(exc)

    if isinstance(exc, (ClientError, BotoCoreError)):
        if isinstance(exc, ClientError):
            error = exc.response.get("Error", {})
            code = error.get("Code")
            message = error.get("Message")
            if code and message:
                return f"{code}: {message}"
            if message:
                return message
        return str(exc)

    return str(exc)
