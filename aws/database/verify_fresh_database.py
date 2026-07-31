#!/usr/bin/env python3
"""Exercise the Airbee application contract against an already-migrated test DB."""

from __future__ import annotations

import json
import os
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from unittest.mock import MagicMock, patch


if os.environ.get("AIRBEE_ALLOW_DATABASE_SMOKE_TEST", "").lower() != "true":
    raise SystemExit(
        "Refusing to modify the database. Set AIRBEE_ALLOW_DATABASE_SMOKE_TEST=true "
        "only for a disposable database."
    )

ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT / "aws" / "backend"
sys.path.insert(0, str(BACKEND_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "airbee.settings")
os.environ.setdefault("DJANGO_SECRET_KEY", "airbee-fresh-database-smoke-test")
os.environ.setdefault("LOCAL_DEV", "true")
os.environ.setdefault("DB_SSLMODE", "disable")
os.environ.setdefault("AIRBEE_API_SURFACE", "all")

import django

django.setup()

from django.db import close_old_connections, connection
from django.test import Client


TENANT_ID = "00000000-0000-0000-0000-000000000001"
ROOM_ID = "00000000-0000-0000-0000-000000000101"
ROOM_TOKEN = "00000000-0000-4000-8000-000000000101"
OTHER_TENANT_ID = "00000000-0000-0000-0000-000000000002"
OTHER_ROOM_ID = "00000000-0000-0000-0000-000000000102"
OTHER_BOOKING_ID = "00000000-0000-0000-0000-000000000202"
PROVISION_SUB = "fresh-database-provisioning-user"


def expect(response, status_code: int, label: str) -> dict:
    if response.status_code != status_code:
        body = response.content.decode("utf-8", errors="replace")
        raise AssertionError(
            f"{label}: expected HTTP {status_code}, got {response.status_code}: {body}"
        )
    if not response.content:
        return {}
    content_type = response.headers.get("Content-Type", "")
    return response.json() if "json" in content_type else {}


def json_post_response(
    client: Client,
    path: str,
    payload: dict,
    *,
    idempotency_key: str | None = None,
):
    response = client.post(
        path,
        data=json.dumps(payload),
        content_type="application/json",
        HTTP_HOST="localhost",
        HTTP_IDEMPOTENCY_KEY=idempotency_key or str(uuid.uuid4()),
    )
    return response


def json_post(
    client: Client,
    path: str,
    payload: dict,
    expected: int = 201,
    *,
    idempotency_key: str | None = None,
) -> dict:
    response = json_post_response(
        client,
        path,
        payload,
        idempotency_key=idempotency_key,
    )
    return expect(response, expected, f"POST {path}")


def seed_contract_fixture() -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            "DELETE FROM tenants WHERE id IN (%s, %s)",
            [TENANT_ID, OTHER_TENANT_ID],
        )
        cursor.execute(
            """
            INSERT INTO tenants (
                id, name, slug, subdomain, primary_hostname,
                booking_site_enabled, settings, booking_theme, contact_email
            )
            VALUES (
                %s, 'Fresh Contract Hotel', 'fresh-contract', 'fresh-contract',
                'fresh-contract.example.com', true,
                '{"booking_site":{"hero_title":"Fresh Contract Hotel"}}'::jsonb,
                '{}'::jsonb, 'owner@example.com'
            )
            """,
            [TENANT_ID],
        )
        cursor.execute(
            """
            INSERT INTO profiles (id, tenant_id, full_name)
            VALUES ('local-dev-user', %s, 'Local Owner')
            """,
            [TENANT_ID],
        )
        cursor.execute(
            """
            INSERT INTO user_roles (user_id, tenant_id, role)
            VALUES ('local-dev-user', %s, 'owner')
            """,
            [TENANT_ID],
        )
        cursor.execute(
            """
            INSERT INTO rooms (
                id, tenant_id, name, max_guests, base_price, status, ical_feed_token
            )
            VALUES (%s, %s, 'Contract Room', 4, 2500, 'available', %s)
            """,
            [ROOM_ID, TENANT_ID, ROOM_TOKEN],
        )
        cursor.execute(
            """
            INSERT INTO tenants (
                id, name, slug, subdomain, primary_hostname,
                booking_site_enabled, settings, booking_theme
            )
            VALUES (
                %s, 'Isolated Hotel', 'isolated-hotel', 'isolated-hotel',
                'isolated-hotel.example.com', true, '{}'::jsonb, '{}'::jsonb
            )
            """,
            [OTHER_TENANT_ID],
        )
        cursor.execute(
            """
            INSERT INTO rooms (id, tenant_id, name, max_guests, base_price, status)
            VALUES (%s, %s, 'Other Tenant Room', 2, 1000, 'available')
            """,
            [OTHER_ROOM_ID, OTHER_TENANT_ID],
        )
        cursor.execute(
            """
            INSERT INTO bookings (
                id, tenant_id, room_id, guest_name, guest_email,
                check_in, check_out, total_amount, base_amount
            )
            VALUES (
                %s, %s, %s, 'Other Tenant Guest', 'isolated@example.com',
                '2035-04-10', '2035-04-12', 2000, 2000
            )
            """,
            [OTHER_BOOKING_ID, OTHER_TENANT_ID, OTHER_ROOM_ID],
        )


def run_smoke_test() -> None:
    seed_contract_fixture()
    client = Client()

    read_endpoints = [
        "/health/live",
        "/health/ready",
        "/api/dashboard/stats",
        "/api/rooms",
        "/api/bookings",
        "/api/guests",
        "/api/housekeeping",
        "/api/pricing-rules",
        "/api/staff",
        "/api/maintenance",
        "/api/expenses",
        "/api/reports/summary",
        "/api/notifications",
        "/api/audit-logs",
        "/api/waitlist",
        "/api/settings",
        "/api/settings/room-categories",
        "/api/messaging",
        "/api/messaging/templates",
        "/api/marketing",
        "/api/marketing/contacts",
        "/api/marketing/segments",
        "/api/channels",
        "/public/properties/fresh-contract?check_in=2035-01-10&check_out=2035-01-12&guests=2",
    ]
    for path in read_endpoints:
        expect(client.get(path, HTTP_HOST="localhost"), 200, f"GET {path}")

    visible_bookings = expect(
        client.get("/api/bookings", HTTP_HOST="localhost"),
        200,
        "tenant-scoped booking list",
    )
    if any(row.get("id") == OTHER_BOOKING_ID for row in visible_bookings):
        raise AssertionError("Booking list exposed another tenant's booking")
    other_tenant_payments = expect(
        client.get(
            f"/api/bookings/{OTHER_BOOKING_ID}/payments",
            HTTP_HOST="localhost",
        ),
        200,
        "cross-tenant payment read",
    )
    if other_tenant_payments:
        raise AssertionError("Payment list exposed another tenant's financial data")
    json_post(
        client,
        f"/api/bookings/{OTHER_BOOKING_ID}/payments",
        {"amount": 100, "payment_method": "cash"},
        expected=404,
    )

    pricing_rule = json_post(
        client,
        "/api/pricing-rules",
        {
            "room_id": ROOM_ID,
            "name": "Fresh database rate",
            "adjustment_type": "percentage",
            "adjustment_value": 10,
            "start_date": "2035-01-01",
            "end_date": "2035-01-31",
            "priority": 5,
        },
    )
    if not pricing_rule.get("id"):
        raise AssertionError("Pricing-rule write did not return an id")

    channel = json_post(
        client,
        "/api/channels",
        {
            "name": "Smoke-test channel",
            "platform": "other",
            "room_id": ROOM_ID,
        },
    )
    if not channel.get("channel", {}).get("id"):
        raise AssertionError("Channel write did not return an id")

    campaign = json_post(
        client,
        "/api/marketing/campaigns",
        {
            "name": "Fresh database campaign",
            "channel": "email",
            "subject": "Contract check",
            "content": "Fresh database contract verified.",
            "segment_key": "all_guests",
        },
    )
    if not campaign.get("id"):
        raise AssertionError("Campaign write did not return an id")

    public_booking_path = "/public/properties/fresh-contract/bookings"
    public_booking_payload = {
        "room_id": ROOM_ID,
        "guest_name": "Contract Guest",
        "guest_email": "contract.guest@example.com",
        "check_in": "2035-02-10",
        "check_out": "2035-02-12",
        "guests": 2,
    }
    missing_key = client.post(
        public_booking_path,
        data=json.dumps(public_booking_payload),
        content_type="application/json",
        HTTP_HOST="localhost",
    )
    missing_key_body = expect(
        missing_key,
        400,
        "public booking without idempotency key",
    )
    if missing_key_body.get("code") != "IDEMPOTENCY_KEY_REQUIRED":
        raise AssertionError("Missing idempotency key did not return a stable error code")

    public_booking_key = str(uuid.uuid4())
    first_booking_response = json_post_response(
        client,
        public_booking_path,
        public_booking_payload,
        idempotency_key=public_booking_key,
    )
    booking = expect(first_booking_response, 201, "initial public booking")
    if first_booking_response.headers.get("Idempotency-Replayed") != "false":
        raise AssertionError("Initial booking was not marked as an original response")

    replay_booking_response = json_post_response(
        client,
        public_booking_path,
        public_booking_payload,
        idempotency_key=public_booking_key,
    )
    replayed_booking = expect(replay_booking_response, 201, "replayed public booking")
    if replay_booking_response.headers.get("Idempotency-Replayed") != "true":
        raise AssertionError("Duplicate booking did not replay the stored response")
    if replayed_booking["booking"]["id"] != booking["booking"]["id"]:
        raise AssertionError("Booking replay returned a different resource")

    mismatched_payload = {**public_booking_payload, "guests": 3}
    mismatched_response = json_post_response(
        client,
        public_booking_path,
        mismatched_payload,
        idempotency_key=public_booking_key,
    )
    mismatched_body = expect(
        mismatched_response,
        409,
        "idempotency key payload mismatch",
    )
    if mismatched_body.get("code") != "IDEMPOTENCY_KEY_REUSED":
        raise AssertionError("Idempotency payload mismatch did not return a stable code")

    overlap_payload = {
        **public_booking_payload,
        "guest_name": "Overlapping Guest",
        "guest_email": "overlap@example.com",
    }
    json_post(
        client,
        public_booking_path,
        overlap_payload,
        expected=409,
    )

    race_barrier = Barrier(2)

    def submit_racing_booking(sequence: int):
        close_old_connections()
        race_client = Client()
        race_payload = {
            "room_id": ROOM_ID,
            "guest_name": f"Concurrent Guest {sequence}",
            "guest_email": f"concurrent{sequence}@example.com",
            "check_in": "2035-06-10",
            "check_out": "2035-06-12",
            "guests": 1,
        }
        race_key = str(uuid.uuid4())
        try:
            race_barrier.wait(timeout=10)
            response = json_post_response(
                race_client,
                "/api/bookings",
                race_payload,
                idempotency_key=race_key,
            )
            body = response.json()
            return response.status_code, body, race_payload, race_key
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        race_results = list(executor.map(submit_racing_booking, (1, 2)))
    if sorted(result[0] for result in race_results) != [201, 409]:
        raise AssertionError(
            f"Concurrent room booking was not serialized safely: {race_results!r}"
        )
    winning_result = next(result for result in race_results if result[0] == 201)
    replay_race = json_post(
        client,
        "/api/bookings",
        winning_result[2],
        idempotency_key=winning_result[3],
    )
    if replay_race["id"] != winning_result[1]["id"]:
        raise AssertionError("Concurrent booking winner was not safely replayable")

    booking_id = booking["booking"]["id"]
    token = booking["guest_access_token"]

    expect(
        client.get(
            f"/public/booking-lookup?token={token}",
            HTTP_HOST="localhost",
        ),
        200,
        "signed booking lookup",
    )

    payment_key = str(uuid.uuid4())
    payment_payload = {"amount": 1000, "payment_method": "cash"}
    payment = json_post(
        client,
        f"/api/bookings/{booking_id}/payments",
        payment_payload,
        idempotency_key=payment_key,
    )
    replay_payment_response = json_post_response(
        client,
        f"/api/bookings/{booking_id}/payments",
        payment_payload,
        idempotency_key=payment_key,
    )
    replayed_payment = expect(replay_payment_response, 201, "replayed booking payment")
    if replay_payment_response.headers.get("Idempotency-Replayed") != "true":
        raise AssertionError("Duplicate payment did not replay the stored response")
    if replayed_payment["id"] != payment["id"]:
        raise AssertionError("Payment replay returned a different resource")
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT count(*), b.amount_paid
            FROM booking_payments bp
            JOIN bookings b ON b.id = bp.booking_id
            WHERE bp.booking_id = %s
            GROUP BY b.amount_paid
            """,
            [booking_id],
        )
        payment_state = cursor.fetchone()
    if payment_state != (1, 1000):
        raise AssertionError(f"Payment replay changed financial state: {payment_state!r}")

    json_post(
        client,
        "/api/invoices",
        {"booking_id": booking_id},
    )
    expect(client.get("/api/invoices", HTTP_HOST="localhost"), 200, "invoice read")

    json_post(
        client,
        "/public/waitlist",
        {
            "tenant_id": TENANT_ID,
            "room_id": ROOM_ID,
            "guest_name": "Waitlist Guest",
            "guest_email": "waitlist.guest@example.com",
            "check_in": "2035-03-10",
            "check_out": "2035-03-12",
            "guests": 2,
        },
    )
    expect(
        client.get(f"/public/ical/{ROOM_TOKEN}.ics", HTTP_HOST="localhost"),
        200,
        "tokenized iCal export",
    )
    json_post(
        client,
        f"/public/bookings/{booking_id}/cancel",
        {"token": token},
        expected=200,
    )
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT count(*) FROM audit_logs WHERE tenant_id = %s",
            [TENANT_ID],
        )
        audit_count = cursor.fetchone()[0]
        cursor.execute(
            "SELECT count(*) FROM api_idempotency_keys WHERE tenant_id = %s",
            [TENANT_ID],
        )
        idempotency_count = cursor.fetchone()[0]
    if audit_count < 4:
        raise AssertionError(
            f"Authenticated mutation auditing did not run; found {audit_count} records"
        )
    if idempotency_count < 2:
        raise AssertionError("Successful mutations were not retained in the idempotency ledger")


def verify_signup_provisioning() -> None:
    trigger_dir = ROOT / "aws" / "cognito-trigger-py"
    sys.path.insert(0, str(trigger_dir))
    import lambda_function

    event = {
        "triggerSource": "PostConfirmation_ConfirmSignUp",
        "userPoolId": "ap-south-1_test",
        "userName": "fresh-contract-user",
        "request": {
            "userAttributes": {
                "sub": PROVISION_SUB,
                "email": "fresh.owner@example.com",
                "name": "Fresh Contract Owner",
            }
        },
    }
    cognito = MagicMock()
    with patch.object(lambda_function.boto3, "client", return_value=cognito):
        lambda_function.handler(event, None)
        lambda_function.handler(event, None)

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT p.tenant_id,
                   count(DISTINCT ur.id) FILTER (WHERE ur.role = 'owner'),
                   count(DISTINCT rc.id)
            FROM profiles p
            LEFT JOIN user_roles ur
              ON ur.user_id = p.id AND ur.tenant_id = p.tenant_id
            LEFT JOIN room_categories rc ON rc.tenant_id = p.tenant_id
            WHERE p.id = %s
            GROUP BY p.tenant_id
            """,
            [PROVISION_SUB],
        )
        row = cursor.fetchone()
    if not row or row[1:] != (1, 4):
        raise AssertionError(f"Signup retry was not idempotent: {row!r}")
    self_service_updates = cognito.admin_update_user_attributes.call_args_list
    if len(self_service_updates) != 2:
        raise AssertionError("Cognito tenant claim was not restored on retry")


def main() -> None:
    try:
        run_smoke_test()
        verify_signup_provisioning()
        print("Fresh database application contract verified.")
    finally:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM tenants
                WHERE id IN (SELECT tenant_id FROM profiles WHERE id = %s)
                """,
                [PROVISION_SUB],
            )
            cursor.execute(
                "DELETE FROM tenants WHERE id IN (%s, %s)",
                [TENANT_ID, OTHER_TENANT_ID],
            )


if __name__ == "__main__":
    main()
