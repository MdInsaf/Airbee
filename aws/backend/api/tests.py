import json
import logging
from unittest.mock import MagicMock, patch
from urllib.parse import urlsplit

from django.http import HttpResponse
from django.test import SimpleTestCase, override_settings
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory

from api.auth import CognitoAuthentication
from api.exceptions import airbee_exception_handler
from api.guest_access import (
    GuestAccessError,
    issue_guest_access_token,
    read_guest_access_token,
)
from api.network_security import SafeFetchError, fetch_ical, validate_public_https_url
from api.observability import (
    JsonFormatter,
    RequestContextMiddleware,
    request_id_context,
    tenant_id_context,
)
from api.views.health import LiveHealthView, ReadyHealthView


class GuestAccessTokenTests(SimpleTestCase):
    def test_token_round_trip_and_tamper_rejection(self):
        token = issue_guest_access_token(
            "11111111-1111-1111-1111-111111111111",
            "22222222-2222-2222-2222-222222222222",
            "Guest@Example.com",
        )

        payload = read_guest_access_token(token)

        self.assertEqual(payload["email"], "guest@example.com")
        self.assertEqual(
            payload["booking_id"],
            "11111111-1111-1111-1111-111111111111",
        )
        with self.assertRaises(GuestAccessError):
            read_guest_access_token(f"{token}tampered")


class OutboundUrlSecurityTests(SimpleTestCase):
    def test_requires_https_and_rejects_credentials(self):
        with self.assertRaises(SafeFetchError):
            validate_public_https_url("http://calendar.example/feed.ics")
        with self.assertRaises(SafeFetchError):
            validate_public_https_url("https://user:password@calendar.example/feed.ics")

    @patch(
        "api.network_security.socket.getaddrinfo",
        return_value=[(2, 1, 6, "", ("127.0.0.1", 443))],
    )
    def test_rejects_private_or_loopback_dns_results(self, _getaddrinfo):
        with self.assertRaises(SafeFetchError):
            validate_public_https_url("https://calendar.example/feed.ics")

    @patch(
        "api.network_security.socket.getaddrinfo",
        return_value=[(2, 1, 6, "", ("93.184.216.34", 443))],
    )
    def test_accepts_a_public_https_destination(self, _getaddrinfo):
        self.assertEqual(
            validate_public_https_url("https://calendar.example/feed.ics"),
            "https://calendar.example/feed.ics",
        )

    @patch("api.network_security.http.client.HTTPSConnection")
    @patch("api.network_security.ssl.create_default_context")
    @patch("api.network_security.socket.create_connection")
    @patch(
        "api.network_security._validated_destination",
        return_value=(
            urlsplit("https://calendar.example/feed.ics"),
            ("93.184.216.34",),
        ),
    )
    def test_fetch_pins_the_validated_address_but_keeps_tls_hostname(
        self,
        _validated,
        create_connection,
        create_context,
        connection_class,
    ):
        raw_socket = MagicMock()
        tls_socket = MagicMock()
        create_connection.return_value = raw_socket
        create_context.return_value.wrap_socket.return_value = tls_socket
        response = MagicMock(status=200)
        response.getheader.return_value = None
        response.read.side_effect = [b"BEGIN:VCALENDAR", b""]
        connection_class.return_value.getresponse.return_value = response

        content = fetch_ical("https://calendar.example/feed.ics")

        self.assertEqual(content, b"BEGIN:VCALENDAR")
        create_connection.assert_called_once_with(("93.184.216.34", 443), timeout=5)
        create_context.return_value.wrap_socket.assert_called_once_with(
            raw_socket,
            server_hostname="calendar.example",
        )
        connection_class.assert_called_once_with("calendar.example", 443, timeout=15)


@override_settings(
    LOCAL_DEV=False,
    COGNITO_USER_POOL_ID="ap-south-1_pool",
    COGNITO_CLIENT_ID="expected-client",
    COGNITO_REGION="ap-south-1",
)
class CognitoAuthenticationTests(SimpleTestCase):
    def setUp(self):
        self.request = APIRequestFactory().get(
            "/api/rooms",
            HTTP_AUTHORIZATION="Bearer signed-token",
        )

    @patch("api.auth.jwt.decode")
    @patch("api.auth.jwt.algorithms.RSAAlgorithm.from_jwk", return_value="public-key")
    @patch("api.auth._get_jwks", return_value={"keys": [{"kid": "key-1"}]})
    @patch("api.auth.jwt.get_unverified_header", return_value={"alg": "RS256", "kid": "key-1"})
    def test_requires_expected_audience_issuer_and_id_token(
        self,
        _header,
        _jwks,
        _from_jwk,
        decode,
    ):
        decode.return_value = {
            "sub": "user-1",
            "email": "owner@example.com",
            "custom:tenant_id": "tenant-1",
            "token_use": "id",
        }

        user, token = CognitoAuthentication().authenticate(self.request)

        self.assertEqual(user.tenant_id, "tenant-1")
        self.assertEqual(user.pk, "user-1")
        self.assertEqual(token, "signed-token")
        self.assertEqual(decode.call_args.kwargs["audience"], "expected-client")
        self.assertEqual(
            decode.call_args.kwargs["issuer"],
            "https://cognito-idp.ap-south-1.amazonaws.com/ap-south-1_pool",
        )
        self.assertEqual(decode.call_args.kwargs["algorithms"], ["RS256"])

    @patch("api.auth.jwt.decode")
    @patch("api.auth.jwt.algorithms.RSAAlgorithm.from_jwk", return_value="public-key")
    @patch("api.auth._get_jwks", return_value={"keys": [{"kid": "key-1"}]})
    @patch("api.auth.jwt.get_unverified_header", return_value={"alg": "RS256", "kid": "key-1"})
    def test_rejects_access_tokens(self, _header, _jwks, _from_jwk, decode):
        decode.return_value = {
            "sub": "user-1",
            "custom:tenant_id": "tenant-1",
            "token_use": "access",
        }

        with self.assertRaises(AuthenticationFailed):
            CognitoAuthentication().authenticate(self.request)


class ObservabilityTests(SimpleTestCase):
    def test_json_formatter_includes_request_and_tenant_context(self):
        request_token = request_id_context.set("request-123")
        tenant_token = tenant_id_context.set("tenant-456")
        try:
            record = logging.LogRecord(
                "airbee.test",
                logging.INFO,
                __file__,
                1,
                "booking_created",
                (),
                None,
            )
            payload = json.loads(JsonFormatter().format(record))
        finally:
            tenant_id_context.reset(tenant_token)
            request_id_context.reset(request_token)

        self.assertEqual(payload["message"], "booking_created")
        self.assertEqual(payload["request_id"], "request-123")
        self.assertEqual(payload["tenant_id"], "tenant-456")

    def test_correlation_middleware_echoes_valid_request_id(self):
        request = APIRequestFactory().get(
            "/health/live",
            HTTP_X_REQUEST_ID="caller-request-123",
        )
        middleware = RequestContextMiddleware(lambda _request: HttpResponse("ok"))

        response = middleware(request)

        self.assertEqual(response["X-Request-ID"], "caller-request-123")

    @patch("api.views.audit_log.log_action")
    def test_successful_authenticated_mutation_is_audited(self, log_action):
        request = APIRequestFactory().post("/api/rooms", {}, format="json")
        request.user = MagicMock(
            tenant_id="00000000-0000-0000-0000-000000000001",
            id="user-1",
        )
        room_id = "00000000-0000-0000-0000-000000000101"
        middleware = RequestContextMiddleware(
            lambda _request: Response({"id": room_id}, status=201)
        )

        middleware(request)

        log_action.assert_called_once()
        self.assertEqual(log_action.call_args.args[1:3], ("create", "rooms"))
        self.assertEqual(log_action.call_args.kwargs["entity_id"], room_id)


class ExceptionHandlerTests(SimpleTestCase):
    @patch("api.exceptions.logger")
    def test_unhandled_errors_are_logged_and_sanitized(self, _logger):
        response = airbee_exception_handler(
            RuntimeError("database password must never be returned"),
            {"view": object()},
        )

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.data["code"], "INTERNAL_ERROR")
        self.assertNotIn("password", response.data["message"])
        self.assertIn("request_id", response.data)


class HealthCheckTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def test_liveness_does_not_require_dependencies(self):
        response = LiveHealthView.as_view()(self.factory.get("/health/live"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "ok")

    @patch("api.views.health.database_is_ready", return_value=True)
    def test_readiness_checks_database(self, _database_is_ready):
        response = ReadyHealthView.as_view()(self.factory.get("/health/ready"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["checks"]["database"], "ok")

    @patch("api.views.health.database_is_ready", return_value=False)
    def test_readiness_is_unavailable_when_database_fails(self, _database_is_ready):
        response = ReadyHealthView.as_view()(self.factory.get("/health/ready"))

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data["checks"]["database"], "failed")


class IdempotencyKeyTests(SimpleTestCase):
    """Test idempotency key handling for safe request replay."""

    def setUp(self):
        from django.core.cache import cache
        self.factory = APIRequestFactory()
        cache.clear()

    def test_idempotency_key_required_for_mutations(self):
        """POST without Idempotency-Key should return 400."""
        from api.idempotency import require_idempotency_key
        from rest_framework.views import APIView

        class TestView(APIView):
            @require_idempotency_key()
            def post(self, request):
                return Response({"id": "123"}, status=201)

        view = TestView.as_view()
        request = self.factory.post("/test/")
        response = view(request)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "IDEMPOTENCY_KEY_REQUIRED")

    def test_idempotency_key_caches_success_response(self):
        """Retry with same key returns cached response."""
        from api.idempotency import require_idempotency_key
        from django.core.cache import cache
        from rest_framework.views import APIView

        call_count = {"value": 0}

        class TestView(APIView):
            @require_idempotency_key()
            def post(self, request):
                call_count["value"] += 1
                return Response({"id": "123", "calls": call_count["value"]}, status=201)

        view = TestView.as_view()

        # First request
        request1 = self.factory.post("/test/", HTTP_IDEMPOTENCY_KEY="key-abc")
        request1.user = MagicMock(tenant_id="tenant-1")
        response1 = view(request1)

        # Second request (should be cached)
        request2 = self.factory.post("/test/", HTTP_IDEMPOTENCY_KEY="key-abc")
        request2.user = MagicMock(tenant_id="tenant-1")
        response2 = view(request2)

        self.assertEqual(response1.status_code, 201)
        self.assertEqual(response2.status_code, 201)
        # Both responses should be identical (from cache)
        self.assertEqual(response1.data, response2.data)
        self.assertEqual(response1.data["calls"], 1)

    def test_idempotency_key_prevents_retry_storms(self):
        """Idempotency key prevents duplicate processing on retries."""
        from api.idempotency import require_idempotency_key
        from django.core.cache import cache
        from rest_framework.views import APIView

        call_count = {"value": 0}

        class TestView(APIView):
            @require_idempotency_key()
            def post(self, request):
                call_count["value"] += 1
                return Response({"processed": True, "call_num": call_count["value"]}, status=201)

        view = TestView.as_view()
        cache.clear()

        # First request with key "unique-123"
        request1 = self.factory.post("/test/", HTTP_IDEMPOTENCY_KEY="unique-123")
        request1.user = MagicMock(tenant_id="tenant-1")
        response1 = view(request1)

        # Retry with same key — should return cached result
        request2 = self.factory.post("/test/", HTTP_IDEMPOTENCY_KEY="unique-123")
        request2.user = MagicMock(tenant_id="tenant-1")
        response2 = view(request2)

        # Retry with different key — should process again
        request3 = self.factory.post("/test/", HTTP_IDEMPOTENCY_KEY="different-456")
        request3.user = MagicMock(tenant_id="tenant-1")
        response3 = view(request3)

        self.assertEqual(response1.status_code, 201)
        self.assertEqual(response2.status_code, 201)
        self.assertEqual(response3.status_code, 201)
        # Same key should return same cached response
        self.assertEqual(response1.data, response2.data)
        # Different key should have been processed
        self.assertNotEqual(response1.data, response3.data)
        self.assertEqual(call_count["value"], 2, "Should only process twice (retry was cached)")


class RequestCorrelationTests(SimpleTestCase):
    """Test request correlation ID tracking and propagation."""

    def setUp(self):
        self.factory = APIRequestFactory()

    def test_request_id_generated_if_not_provided(self):
        """If no X-Request-ID header, one should be generated."""
        from api.observability import RequestContextMiddleware
        from rest_framework.views import APIView

        class TestView(APIView):
            def get(self, request):
                return Response({"request_id": getattr(request, "request_id", None)})

        get_response = TestView.as_view()
        middleware = RequestContextMiddleware(get_response)
        request = self.factory.get("/test/")
        response = middleware(request)

        self.assertIsNotNone(response.data["request_id"])
        self.assertGreater(len(response.data["request_id"]), 0)

    def test_request_id_from_header_preserved(self):
        """X-Request-ID header should be used if provided."""
        from api.observability import RequestContextMiddleware
        from rest_framework.views import APIView

        class TestView(APIView):
            def get(self, request):
                return Response({"request_id": getattr(request, "request_id", None)})

        get_response = TestView.as_view()
        middleware = RequestContextMiddleware(get_response)
        request = self.factory.get("/test/", HTTP_X_REQUEST_ID="custom-123")
        response = middleware(request)

        self.assertEqual(response.data["request_id"], "custom-123")
        self.assertEqual(response["X-Request-ID"], "custom-123")

    def test_invalid_request_id_generates_new_one(self):
        """Invalid X-Request-ID should generate a new one."""
        from api.observability import RequestContextMiddleware
        from rest_framework.views import APIView

        class TestView(APIView):
            def get(self, request):
                return Response({"request_id": getattr(request, "request_id", None)})

        get_response = TestView.as_view()
        middleware = RequestContextMiddleware(get_response)
        # Request ID with invalid characters (not printable ASCII)
        request = self.factory.get("/test/", HTTP_X_REQUEST_ID="\x00\x01invalid")
        response = middleware(request)

        # Should have generated a new valid ID
        self.assertIsNotNone(response.data["request_id"])
        self.assertNotIn("\x00", response.data["request_id"])


# ════════════════════════════════════════════════════════════════════════════
# Integration Tests: API → Database → Response
# ════════════════════════════════════════════════════════════════════════════

from django.test import TransactionTestCase
from rest_framework.test import APITransactionTestCase
from django.db import connection
import uuid


class BookingIntegrationTests(APITransactionTestCase):
    """Test booking creation, retrieval, and updates with real database."""

    def setUp(self):
        """Create test tenant and room."""
        self.tenant_id = "11111111-1111-1111-1111-111111111111"
        self.room_id = "22222222-2222-2222-2222-222222222222"
        self.user_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"

        with connection.cursor() as cur:
            # Create tenant
            cur.execute(
                """INSERT INTO tenants (id, name, slug, booking_site_enabled)
                   VALUES (%s, %s, %s, %s)""",
                [self.tenant_id, "Test Hotel", "test-hotel", True],
            )
            # Create room
            cur.execute(
                """INSERT INTO rooms (id, tenant_id, name, room_number, base_price, max_guests, status)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                [self.room_id, self.tenant_id, "Room 101", "101", 100.0, 2, "available"],
            )
        connection.commit()

        # Create authenticated client
        self.client.force_authenticate(
            user=MagicMock(
                tenant_id=self.tenant_id,
                sub=self.user_id,
                is_authenticated=True,
            )
        )

    def test_create_booking_persists_to_database(self):
        """POST /api/bookings creates booking in database."""
        booking_id = str(uuid.uuid4())

        response = self.client.post(
            "/api/bookings",
            {
                "id": booking_id,
                "room_id": str(self.room_id),
                "guest_name": "John Doe",
                "guest_email": "john@example.com",
                "check_in": "2026-08-01",
                "check_out": "2026-08-03",
                "guests": 2,
                "status": "pending",
                "payment_status": "unpaid",
            },
            format="json",
        )

        # Verify API response
        self.assertEqual(response.status_code, 201)
        self.assertIn("id", response.data)

        # Verify database record
        with connection.cursor() as cur:
            cur.execute(
                "SELECT id, guest_name, status FROM bookings WHERE id = %s AND tenant_id = %s",
                [booking_id, self.tenant_id],
            )
            booking = cur.fetchone()

        self.assertIsNotNone(booking, "Booking should be persisted to database")
        self.assertEqual(booking[1], "John Doe")
        self.assertEqual(booking[2], "pending")

    def test_list_bookings_filters_by_tenant(self):
        """GET /api/bookings returns only tenant's bookings."""
        other_tenant_id = "33333333-3333-3333-3333-333333333333"
        other_room_id = "44444444-4444-4444-4444-444444444444"

        with connection.cursor() as cur:
            # Create other tenant's room
            cur.execute(
                """INSERT INTO rooms (id, tenant_id, name, room_number, base_price, max_guests, status)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                [
                    other_room_id,
                    other_tenant_id,
                    "Room 201",
                    "201",
                    120.0,
                    2,
                    "available",
                ],
            )
            # Create bookings for both tenants
            booking_1 = str(uuid.uuid4())
            booking_2 = str(uuid.uuid4())
            cur.execute(
                """INSERT INTO bookings
                   (id, tenant_id, room_id, guest_name, check_in, check_out, status, payment_status)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                [
                    booking_1,
                    self.tenant_id,
                    self.room_id,
                    "Guest 1",
                    "2026-08-01",
                    "2026-08-03",
                    "confirmed",
                    "paid",
                ],
            )
            cur.execute(
                """INSERT INTO bookings
                   (id, tenant_id, room_id, guest_name, check_in, check_out, status, payment_status)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                [
                    booking_2,
                    other_tenant_id,
                    other_room_id,
                    "Guest 2",
                    "2026-08-05",
                    "2026-08-07",
                    "confirmed",
                    "paid",
                ],
            )

        response = self.client.get("/api/bookings", format="json")

        self.assertEqual(response.status_code, 200)
        # Should only see our tenant's booking
        self.assertGreaterEqual(len(response.data), 1)
        booking_ids = [b.get("id") for b in response.data]
        self.assertIn(booking_1, booking_ids)
        self.assertNotIn(booking_2, booking_ids)


class PaymentIntegrationTests(APITransactionTestCase):
    """Test payment creation and idempotency."""

    def setUp(self):
        """Create test data."""
        self.tenant_id = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
        self.room_id = "cccccccc-cccc-cccc-cccc-cccccccccccc"
        self.booking_id = "dddddddd-dddd-dddd-dddd-dddddddddddd"
        self.user_id = "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee"

        with connection.cursor() as cur:
            # Create tenant and room
            cur.execute(
                "INSERT INTO tenants (id, name, slug, booking_site_enabled) VALUES (%s, %s, %s, %s)",
                [self.tenant_id, "Payment Test Hotel", "payment-hotel", True],
            )
            cur.execute(
                """INSERT INTO rooms (id, tenant_id, name, room_number, base_price, max_guests, status)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                [self.room_id, self.tenant_id, "Room 500", "500", 200.0, 2, "available"],
            )
            # Create booking
            cur.execute(
                """INSERT INTO bookings
                   (id, tenant_id, room_id, guest_name, check_in, check_out, status, payment_status)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                [
                    self.booking_id,
                    self.tenant_id,
                    self.room_id,
                    "Payment Guest",
                    "2026-08-10",
                    "2026-08-12",
                    "confirmed",
                    "unpaid",
                ],
            )

        self.client.force_authenticate(
            user=MagicMock(
                tenant_id=self.tenant_id,
                sub=self.user_id,
                is_authenticated=True,
            )
        )

    def test_create_payment_persists_to_database(self):
        """POST /api/bookings/<id>/payments creates payment record."""
        response = self.client.post(
            f"/api/bookings/{self.booking_id}/payments",
            {
                "amount": 100.0,
                "payment_method": "card",
                "payment_date": "2026-08-10",
                "notes": "Partial payment",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)

        # Verify payment in database
        with connection.cursor() as cur:
            cur.execute(
                "SELECT amount, payment_method FROM booking_payments WHERE booking_id = %s",
                [self.booking_id],
            )
            payment = cur.fetchone()

        self.assertIsNotNone(payment)
        self.assertEqual(float(payment[0]), 100.0)
        self.assertEqual(payment[1], "card")


class TenantIsolationTests(APITransactionTestCase):
    """Test multi-tenant isolation at API level."""

    def setUp(self):
        """Create two separate tenants."""
        self.tenant_a_id = "f1f1f1f1-f1f1-f1f1-f1f1-f1f1f1f1f1f1"
        self.tenant_b_id = "f2f2f2f2-f2f2-f2f2-f2f2-f2f2f2f2f2f2"
        self.room_a_id = "a1a1a1a1-a1a1-a1a1-a1a1-a1a1a1a1a1a1"
        self.room_b_id = "b1b1b1b1-b1b1-b1b1-b1b1-b1b1b1b1b1b1"

        with connection.cursor() as cur:
            # Create two tenants
            cur.execute(
                "INSERT INTO tenants (id, name, slug, booking_site_enabled) VALUES (%s, %s, %s, %s)",
                [self.tenant_a_id, "Hotel A", "hotel-a", True],
            )
            cur.execute(
                "INSERT INTO tenants (id, name, slug, booking_site_enabled) VALUES (%s, %s, %s, %s)",
                [self.tenant_b_id, "Hotel B", "hotel-b", True],
            )
            # Create room for each tenant
            cur.execute(
                """INSERT INTO rooms (id, tenant_id, name, room_number, base_price, max_guests, status)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                [self.room_a_id, self.tenant_a_id, "Room A1", "A1", 100.0, 2, "available"],
            )
            cur.execute(
                """INSERT INTO rooms (id, tenant_id, name, room_number, base_price, max_guests, status)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                [self.room_b_id, self.tenant_b_id, "Room B1", "B1", 150.0, 2, "available"],
            )

    def test_tenant_cannot_see_other_rooms(self):
        """Tenant A's API client should not see Tenant B's rooms."""
        self.client.force_authenticate(
            user=MagicMock(
                tenant_id=self.tenant_a_id,
                sub="user-a",
                is_authenticated=True,
            )
        )

        response = self.client.get("/api/rooms", format="json")

        self.assertEqual(response.status_code, 200)
        room_ids = [r.get("id") for r in response.data if isinstance(r, dict)]
        # Should see own room
        self.assertIn(self.room_a_id, room_ids)
        # Should NOT see other tenant's room
        self.assertNotIn(self.room_b_id, room_ids)
# ════════════════════════════════════════════════════════════════════════════
# Integration Tests: API → Database → Response
# ════════════════════════════════════════════════════════════════════════════

from django.test import TransactionTestCase
from rest_framework.test import APITransactionTestCase
from django.db import connection
import uuid


class BookingIntegrationTests(APITransactionTestCase):
    """Test booking creation, retrieval, and updates with real database."""

    def setUp(self):
        """Create test tenant and room."""
        self.tenant_id = "11111111-1111-1111-1111-111111111111"
        self.room_id = "22222222-2222-2222-2222-222222222222"
        self.user_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"

        with connection.cursor() as cur:
            # Create tenant
            cur.execute(
                """INSERT INTO tenants (id, name, slug, booking_site_enabled)
                   VALUES (%s, %s, %s, %s)""",
                [self.tenant_id, "Test Hotel", "test-hotel", True],
            )
            # Create room
            cur.execute(
                """INSERT INTO rooms (id, tenant_id, name, room_number, base_price, max_guests, status)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                [self.room_id, self.tenant_id, "Room 101", "101", 100.0, 2, "available"],
            )
        connection.commit()

        # Create authenticated client
        self.client.force_authenticate(
            user=MagicMock(
                tenant_id=self.tenant_id,
                sub=self.user_id,
                is_authenticated=True,
            )
        )

    def test_create_booking_persists_to_database(self):
        """POST /api/bookings creates booking in database."""
        booking_id = str(uuid.uuid4())

        response = self.client.post(
            "/api/bookings",
            {
                "id": booking_id,
                "room_id": str(self.room_id),
                "guest_name": "John Doe",
                "guest_email": "john@example.com",
                "check_in": "2026-08-01",
                "check_out": "2026-08-03",
                "guests": 2,
                "status": "pending",
                "payment_status": "unpaid",
            },
            format="json",
        )

        # Verify API response
        self.assertEqual(response.status_code, 201)
        self.assertIn("id", response.data)

        # Verify database record
        with connection.cursor() as cur:
            cur.execute(
                "SELECT id, guest_name, status FROM bookings WHERE id = %s AND tenant_id = %s",
                [booking_id, self.tenant_id],
            )
            booking = cur.fetchone()

        self.assertIsNotNone(booking, "Booking should be persisted to database")
        self.assertEqual(booking[1], "John Doe")
        self.assertEqual(booking[2], "pending")

    def test_list_bookings_filters_by_tenant(self):
        """GET /api/bookings returns only tenant's bookings."""
        other_tenant_id = "33333333-3333-3333-3333-333333333333"
        other_room_id = "44444444-4444-4444-4444-444444444444"

        with connection.cursor() as cur:
            # Create other tenant's room
            cur.execute(
                """INSERT INTO rooms (id, tenant_id, name, room_number, base_price, max_guests, status)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                [
                    other_room_id,
                    other_tenant_id,
                    "Room 201",
                    "201",
                    120.0,
                    2,
                    "available",
                ],
            )
            # Create bookings for both tenants
            booking_1 = str(uuid.uuid4())
            booking_2 = str(uuid.uuid4())
            cur.execute(
                """INSERT INTO bookings
                   (id, tenant_id, room_id, guest_name, check_in, check_out, status, payment_status)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                [
                    booking_1,
                    self.tenant_id,
                    self.room_id,
                    "Guest 1",
                    "2026-08-01",
                    "2026-08-03",
                    "confirmed",
                    "paid",
                ],
            )
            cur.execute(
                """INSERT INTO bookings
                   (id, tenant_id, room_id, guest_name, check_in, check_out, status, payment_status)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                [
                    booking_2,
                    other_tenant_id,
                    other_room_id,
                    "Guest 2",
                    "2026-08-05",
                    "2026-08-07",
                    "confirmed",
                    "paid",
                ],
            )

        response = self.client.get("/api/bookings", format="json")

        self.assertEqual(response.status_code, 200)
        # Should only see our tenant's booking
        self.assertGreaterEqual(len(response.data), 1)
        booking_ids = [b.get("id") for b in response.data]
        self.assertIn(booking_1, booking_ids)
        self.assertNotIn(booking_2, booking_ids)


class PaymentIntegrationTests(APITransactionTestCase):
    """Test payment creation and idempotency."""

    def setUp(self):
        """Create test data."""
        self.tenant_id = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
        self.room_id = "cccccccc-cccc-cccc-cccc-cccccccccccc"
        self.booking_id = "dddddddd-dddd-dddd-dddd-dddddddddddd"
        self.user_id = "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee"

        with connection.cursor() as cur:
            # Create tenant and room
            cur.execute(
                "INSERT INTO tenants (id, name, slug, booking_site_enabled) VALUES (%s, %s, %s, %s)",
                [self.tenant_id, "Payment Test Hotel", "payment-hotel", True],
            )
            cur.execute(
                """INSERT INTO rooms (id, tenant_id, name, room_number, base_price, max_guests, status)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                [self.room_id, self.tenant_id, "Room 500", "500", 200.0, 2, "available"],
            )
            # Create booking
            cur.execute(
                """INSERT INTO bookings
                   (id, tenant_id, room_id, guest_name, check_in, check_out, status, payment_status)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                [
                    self.booking_id,
                    self.tenant_id,
                    self.room_id,
                    "Payment Guest",
                    "2026-08-10",
                    "2026-08-12",
                    "confirmed",
                    "unpaid",
                ],
            )

        self.client.force_authenticate(
            user=MagicMock(
                tenant_id=self.tenant_id,
                sub=self.user_id,
                is_authenticated=True,
            )
        )

    def test_create_payment_persists_to_database(self):
        """POST /api/bookings/<id>/payments creates payment record."""
        response = self.client.post(
            f"/api/bookings/{self.booking_id}/payments",
            {
                "amount": 100.0,
                "payment_method": "card",
                "payment_date": "2026-08-10",
                "notes": "Partial payment",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)

        # Verify payment in database
        with connection.cursor() as cur:
            cur.execute(
                "SELECT amount, payment_method FROM booking_payments WHERE booking_id = %s",
                [self.booking_id],
            )
            payment = cur.fetchone()

        self.assertIsNotNone(payment)
        self.assertEqual(float(payment[0]), 100.0)
        self.assertEqual(payment[1], "card")


class TenantIsolationTests(APITransactionTestCase):
    """Test multi-tenant isolation at API level."""

    def setUp(self):
        """Create two separate tenants."""
        self.tenant_a_id = "f1f1f1f1-f1f1-f1f1-f1f1-f1f1f1f1f1f1"
        self.tenant_b_id = "f2f2f2f2-f2f2-f2f2-f2f2-f2f2f2f2f2f2"
        self.room_a_id = "a1a1a1a1-a1a1-a1a1-a1a1-a1a1a1a1a1a1"
        self.room_b_id = "b1b1b1b1-b1b1-b1b1-b1b1-b1b1b1b1b1b1"

        with connection.cursor() as cur:
            # Create two tenants
            cur.execute(
                "INSERT INTO tenants (id, name, slug, booking_site_enabled) VALUES (%s, %s, %s, %s)",
                [self.tenant_a_id, "Hotel A", "hotel-a", True],
            )
            cur.execute(
                "INSERT INTO tenants (id, name, slug, booking_site_enabled) VALUES (%s, %s, %s, %s)",
                [self.tenant_b_id, "Hotel B", "hotel-b", True],
            )
            # Create room for each tenant
            cur.execute(
                """INSERT INTO rooms (id, tenant_id, name, room_number, base_price, max_guests, status)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                [self.room_a_id, self.tenant_a_id, "Room A1", "A1", 100.0, 2, "available"],
            )
            cur.execute(
                """INSERT INTO rooms (id, tenant_id, name, room_number, base_price, max_guests, status)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                [self.room_b_id, self.tenant_b_id, "Room B1", "B1", 150.0, 2, "available"],
            )

    def test_tenant_cannot_see_other_rooms(self):
        """Tenant A's API client should not see Tenant B's rooms."""
        self.client.force_authenticate(
            user=MagicMock(
                tenant_id=self.tenant_a_id,
                sub="user-a",
                is_authenticated=True,
            )
        )

        response = self.client.get("/api/rooms", format="json")

        self.assertEqual(response.status_code, 200)
        room_ids = [r.get("id") for r in response.data if isinstance(r, dict)]
        # Should see own room
        self.assertIn(self.room_a_id, room_ids)
        # Should NOT see other tenant's room
        self.assertNotIn(self.room_b_id, room_ids)
