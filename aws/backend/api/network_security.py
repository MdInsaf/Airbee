"""Outbound URL validation for tenant-configured integrations."""

from __future__ import annotations

import ipaddress
import http.client
import os
import socket
import ssl
from urllib.parse import urljoin, urlsplit, urlunsplit


MAX_ICAL_BYTES = 2 * 1024 * 1024
MAX_REDIRECTS = 3


class SafeFetchError(ValueError):
    pass


def _allowed_hostnames() -> tuple[str, ...]:
    return tuple(
        item.strip().lower().rstrip(".")
        for item in os.environ.get("ICAL_ALLOWED_HOSTS", "").split(",")
        if item.strip()
    )


def _is_allowlisted(hostname: str) -> bool:
    allowlist = _allowed_hostnames()
    if not allowlist:
        return True
    return any(hostname == item or hostname.endswith(f".{item}") for item in allowlist)


def _validated_destination(url: str):
    try:
        parsed = urlsplit(str(url or "").strip())
    except ValueError as exc:
        raise SafeFetchError("The iCal URL is invalid") from exc

    if parsed.scheme.lower() != "https":
        raise SafeFetchError("The iCal URL must use HTTPS")
    if parsed.username or parsed.password:
        raise SafeFetchError("The iCal URL cannot contain credentials")
    if not parsed.hostname:
        raise SafeFetchError("The iCal URL must include a hostname")

    hostname = parsed.hostname.lower().rstrip(".")
    if not _is_allowlisted(hostname):
        raise SafeFetchError("The iCal hostname is not in the server allowlist")

    try:
        port = parsed.port or 443
        addresses = {
            item[4][0]
            for item in socket.getaddrinfo(
                hostname,
                port,
                type=socket.SOCK_STREAM,
            )
        }
    except (socket.gaierror, ValueError) as exc:
        raise SafeFetchError("The iCal hostname could not be resolved") from exc

    if not addresses:
        raise SafeFetchError("The iCal hostname did not resolve to an address")

    for raw_address in addresses:
        address = ipaddress.ip_address(raw_address)
        if not address.is_global:
            raise SafeFetchError("The iCal hostname resolves to a non-public address")

    return parsed, tuple(sorted(addresses))


def validate_public_https_url(url: str) -> str:
    parsed, _addresses = _validated_destination(url)
    return parsed.geturl()


def fetch_ical(url: str) -> bytes:
    current_url = str(url or "").strip()
    headers = {
        "Accept": "text/calendar, application/ics, text/plain;q=0.8",
        "User-Agent": "Airbee-Channel-Sync/1.0",
    }

    for redirect_count in range(MAX_REDIRECTS + 1):
        parsed, addresses = _validated_destination(current_url)
        hostname = parsed.hostname
        port = parsed.port or 443
        request_target = urlunsplit(("", "", parsed.path or "/", parsed.query, ""))
        host_header = hostname if port == 443 else f"{hostname}:{port}"
        response = None
        connection = None
        last_error = None

        # Connect to an address that was validated above, while preserving the
        # original hostname for SNI and certificate validation. This prevents a
        # second DNS lookup from being changed to a private address (DNS rebinding).
        for address in addresses:
            raw_socket = None
            try:
                raw_socket = socket.create_connection((address, port), timeout=5)
                tls_socket = ssl.create_default_context().wrap_socket(
                    raw_socket,
                    server_hostname=hostname,
                )
                tls_socket.settimeout(15)
                connection = http.client.HTTPSConnection(hostname, port, timeout=15)
                connection.sock = tls_socket
                request_headers = {**headers, "Host": host_header}
                connection.request("GET", request_target, headers=request_headers)
                response = connection.getresponse()
                break
            except (OSError, ssl.SSLError, http.client.HTTPException) as exc:
                last_error = exc
                if connection:
                    connection.close()
                elif raw_socket:
                    raw_socket.close()
                connection = None

        if response is None:
            raise SafeFetchError("The iCal provider could not be reached") from last_error

        try:
            if response.status in {301, 302, 303, 307, 308}:
                if redirect_count >= MAX_REDIRECTS:
                    raise SafeFetchError("The iCal provider redirected too many times")
                location = response.getheader("Location")
                if not location:
                    raise SafeFetchError("The iCal provider returned an invalid redirect")
                current_url = urljoin(parsed.geturl(), location)
                continue

            if response.status < 200 or response.status >= 300:
                raise SafeFetchError("The iCal provider returned an error response")

            content_length = response.getheader("Content-Length")
            if content_length:
                try:
                    if int(content_length) > MAX_ICAL_BYTES:
                        raise SafeFetchError("The iCal response is too large")
                except ValueError:
                    pass

            chunks = []
            total = 0
            while True:
                chunk = response.read(64 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_ICAL_BYTES:
                    raise SafeFetchError("The iCal response is too large")
                chunks.append(chunk)
            return b"".join(chunks)
        except (OSError, ssl.SSLError, http.client.HTTPException) as exc:
            raise SafeFetchError("The iCal provider could not be reached") from exc
        finally:
            connection.close()

    raise SafeFetchError("The iCal provider could not be reached")
