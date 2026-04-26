"""
AWS SES email utility for transactional booking emails.
All functions are best-effort — they log failures but never raise,
so email errors never break the booking flow.
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import date
from decimal import Decimal
from typing import Any

import boto3
from botocore.exceptions import ClientError
from django.db import connection

logger = logging.getLogger(__name__)

SES_REGION = os.environ.get("SES_REGION", "ap-south-1")
SES_FROM_EMAIL = os.environ.get("SES_FROM_EMAIL", "bookings@ascendersservices.in")
SES_ENABLED = os.environ.get("SES_ENABLED", "true").lower() not in ("false", "0", "no")
ADMIN_NOTIFY_EMAIL = os.environ.get("ADMIN_NOTIFY_EMAIL", "mohamedinsaf8.mi@gmail.com")


# ── Formatting helpers ───────────────────────────────────────────────────────

def _fmt_currency(amount: Any, currency: str = "INR") -> str:
    try:
        val = float(amount or 0)
        if currency == "INR":
            return f"₹{val:,.0f}"
        return f"{currency} {val:,.2f}"
    except Exception:
        return str(amount or "—")


def _fmt_date(raw: Any) -> str:
    if not raw:
        return "—"
    try:
        if isinstance(raw, (date,)):
            d = raw
        else:
            from datetime import datetime
            d = datetime.fromisoformat(str(raw).replace("Z", "+00:00")).date()
        return d.strftime("%d %B %Y")
    except Exception:
        return str(raw)


# ── HTML email templates ─────────────────────────────────────────────────────

_BASE_STYLE = """
  body { margin:0; padding:0; background:#f5f5f0; font-family:'Helvetica Neue',Arial,sans-serif; color:#1a1a1a; }
  .wrap { max-width:600px; margin:32px auto; background:#ffffff; border-radius:12px; overflow:hidden; box-shadow:0 2px 12px rgba(0,0,0,0.08); }
  .header { background:linear-gradient(135deg,#1a3a2a 0%,#2d5a3d 100%); padding:32px 40px; text-align:center; }
  .header h1 { margin:0; color:#d4b483; font-size:24px; font-weight:300; letter-spacing:2px; text-transform:uppercase; }
  .header p { margin:6px 0 0; color:rgba(255,255,255,0.7); font-size:13px; }
  .body { padding:36px 40px; }
  .greeting { font-size:18px; font-weight:600; margin-bottom:8px; }
  .subtitle { color:#666; font-size:14px; margin-bottom:28px; }
  .booking-card { background:#f9f7f4; border:1px solid #e8e4dc; border-radius:10px; padding:24px; margin:24px 0; }
  .booking-card h3 { margin:0 0 16px; font-size:13px; text-transform:uppercase; letter-spacing:1px; color:#888; }
  .row { display:flex; justify-content:space-between; padding:8px 0; border-bottom:1px solid #ede9e2; font-size:14px; }
  .row:last-child { border-bottom:none; }
  .row .label { color:#666; }
  .row .value { font-weight:600; color:#1a1a1a; }
  .total-row { background:#1a3a2a; border-radius:8px; padding:14px 20px; margin-top:16px; display:flex; justify-content:space-between; }
  .total-row .label { color:rgba(255,255,255,0.75); font-size:14px; }
  .total-row .value { color:#d4b483; font-size:18px; font-weight:700; }
  .status-badge { display:inline-block; padding:4px 14px; border-radius:20px; font-size:12px; font-weight:700; text-transform:uppercase; letter-spacing:1px; }
  .status-pending { background:#fff3cd; color:#856404; }
  .status-confirmed { background:#d1fae5; color:#065f46; }
  .highlight { background:#fffbf0; border-left:3px solid #d4b483; padding:14px 18px; border-radius:0 8px 8px 0; margin:20px 0; font-size:14px; color:#555; }
  .footer { background:#f0ede8; padding:24px 40px; text-align:center; font-size:12px; color:#999; border-top:1px solid #e8e4dc; }
  .footer a { color:#2d5a3d; text-decoration:none; }
  .footer strong { color:#555; }
  .divider { height:1px; background:#ede9e2; margin:20px 0; }
  .cta { text-align:center; margin:28px 0; }
  .cta a { background:#1a3a2a; color:#d4b483; text-decoration:none; padding:14px 32px; border-radius:8px; font-size:14px; font-weight:600; letter-spacing:0.5px; display:inline-block; }
"""


def _build_email_html(*, subject_line: str, property_name: str, body_html: str, contact_email: str = "", contact_phone: str = "") -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{subject_line}</title>
<style>{_BASE_STYLE}</style>
</head>
<body>
<div class="wrap">
  <div class="header">
    <h1>{property_name}</h1>
    <p>Booking Confirmation</p>
  </div>
  <div class="body">
    {body_html}
  </div>
  <div class="footer">
    <strong>{property_name}</strong><br/>
    {"<a href='mailto:" + contact_email + "'>" + contact_email + "</a> &nbsp;·&nbsp;" if contact_email else ""}
    {contact_phone + " &nbsp;·&nbsp;" if contact_phone else ""}
    <br/><br/>
    <span>This is an automated email from AIR BEE — Hospitality Management Platform.</span>
  </div>
</div>
</body>
</html>"""


def _pending_email_body(booking: dict, room: dict, pricing: dict, property_data: dict) -> str:
    currency = property_data.get("currency", "INR")
    guest_portal_url = f"https://{property_data.get('primary_hostname', 'booking.ascendersservices.in')}/my-booking"
    nights = pricing.get("nights", 0)

    rows = [
        ("Booking Reference", f"<span style='font-family:monospace'>{str(booking.get('id',''))[:8].upper()}</span>"),
        ("Room", room.get("name", "—")),
        ("Check-in", _fmt_date(booking.get("check_in"))),
        ("Check-out", _fmt_date(booking.get("check_out"))),
        ("Nights", f"{nights} night{'s' if nights != 1 else ''}"),
        ("Guests", str(booking.get("guests", 1))),
    ]
    if room.get("check_in_time"):
        rows.append(("Check-in time", room["check_in_time"]))
    if room.get("check_out_time"):
        rows.append(("Check-out time", room["check_out_time"]))

    pricing_rows = [("Room charges", _fmt_currency(pricing.get("base_amount", 0), currency))]
    if pricing.get("extra_guest_total", 0):
        pricing_rows.append(("Extra guests", _fmt_currency(pricing["extra_guest_total"], currency)))
    if pricing.get("tax_amount", 0):
        pricing_rows.append(("Taxes & GST", _fmt_currency(pricing["tax_amount"], currency)))
    if pricing.get("service_charge", 0):
        pricing_rows.append(("Service charge", _fmt_currency(pricing["service_charge"], currency)))

    detail_html = "".join(
        f'<div class="row"><span class="label">{label}</span><span class="value">{value}</span></div>'
        for label, value in rows
    )
    pricing_html = "".join(
        f'<div class="row"><span class="label">{label}</span><span class="value">{value}</span></div>'
        for label, value in pricing_rows
    )

    return f"""
    <p class="greeting">Hello {booking.get('guest_name', 'Guest')},</p>
    <p class="subtitle">Thank you for choosing {property_data.get('name', 'our property')}. We've received your reservation request and will confirm it shortly.</p>

    <div class="booking-card">
      <h3>Reservation Details</h3>
      {detail_html}
    </div>

    <div class="booking-card">
      <h3>Pricing</h3>
      {pricing_html}
      <div class="total-row" style="display:table;width:100%;box-sizing:border-box;margin-top:16px;background:#1a3a2a;border-radius:8px;padding:14px 20px;">
        <span style="color:rgba(255,255,255,0.75);font-size:14px;">Total Amount</span>
        <span style="float:right;color:#d4b483;font-size:18px;font-weight:700;">{_fmt_currency(pricing.get('total_amount', 0), currency)}</span>
      </div>
    </div>

    <div class="highlight">
      Your booking status is currently <strong>pending</strong>. You will receive another email once our team confirms your reservation. Payment is collected at the property.
    </div>

    {f'<div class="cta"><a href="{guest_portal_url}">View My Booking</a></div>' if guest_portal_url else ""}

    {"<p style='font-size:13px;color:#666;'><strong>Cancellation policy:</strong> " + room['cancellation_policy'] + "</p>" if room.get('cancellation_policy') else ""}

    <p style="font-size:13px;color:#888;">Questions? Reply to this email or contact us directly.</p>
    """


def _confirmed_email_body(booking: dict, room_name: str, property_data: dict) -> str:
    currency = property_data.get("currency", "INR")
    guest_portal_url = f"https://{property_data.get('primary_hostname', 'booking.ascendersservices.in')}/my-booking"
    address = property_data.get("address", "")

    rows = [
        ("Booking Reference", f"<span style='font-family:monospace'>{str(booking.get('id',''))[:8].upper()}</span>"),
        ("Room", room_name or "—"),
        ("Check-in", _fmt_date(booking.get("check_in"))),
        ("Check-out", _fmt_date(booking.get("check_out"))),
        ("Guests", str(booking.get("guests", 1))),
        ("Total Amount", _fmt_currency(booking.get("total_amount", 0), currency)),
        ("Payment Status", str(booking.get("payment_status", "unpaid")).capitalize()),
    ]
    detail_html = "".join(
        f'<div class="row"><span class="label">{label}</span><span class="value">{value}</span></div>'
        for label, value in rows
    )

    return f"""
    <p class="greeting">Great news, {booking.get('guest_name', 'Guest')}!</p>
    <p class="subtitle">Your reservation at <strong>{property_data.get('name', 'our property')}</strong> has been <strong style="color:#065f46;">confirmed</strong>. We look forward to welcoming you.</p>

    <div class="booking-card">
      <h3>Confirmed Reservation</h3>
      {detail_html}
    </div>

    {f'<div class="highlight">📍 <strong>Address:</strong> {address}</div>' if address else ""}

    {f'<div class="cta"><a href="{guest_portal_url}">View My Booking</a></div>' if guest_portal_url else ""}

    <p style="font-size:13px;color:#888;">Need to make changes? Contact us as soon as possible. We're happy to help.</p>
    """


# ── SES send helper ──────────────────────────────────────────────────────────

def _send_ses(*, to_email: str, subject: str, html_body: str, from_email: str | None = None, bcc_emails: list[str] | None = None) -> bool:
    if not SES_ENABLED:
        logger.info("SES disabled — skipping email to %s", to_email)
        return False
    sender = from_email or SES_FROM_EMAIL
    destination: dict = {"ToAddresses": [to_email]}
    if bcc_emails:
        destination["BccAddresses"] = [e for e in bcc_emails if e and e != to_email]
    try:
        client = boto3.client("ses", region_name=SES_REGION)
        client.send_email(
            Source=sender,
            Destination=destination,
            Message={
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {"Html": {"Data": html_body, "Charset": "UTF-8"}},
            },
        )
        logger.info("SES email sent to %s — %s", to_email, subject)
        return True
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code == "MessageRejected":
            logger.warning("SES rejected email to %s: %s — SES sandbox may be active", to_email, exc)
        elif code in ("InvalidClientTokenId", "SignatureDoesNotMatch"):
            logger.warning("SES auth error: %s", exc)
        else:
            logger.warning("SES send failed to %s: %s", to_email, exc)
        return False
    except Exception as exc:
        logger.warning("SES unexpected error: %s", exc)
        return False


def _log_email(tenant_id: str, *, to_email: str, email_type: str, subject: str, status: str) -> None:
    try:
        with connection.cursor() as cur:
            cur.execute(
                """
                INSERT INTO email_logs (id, tenant_id, email_type, recipient, subject, status)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                [str(uuid.uuid4()), tenant_id, email_type, to_email, subject, status],
            )
    except Exception:
        pass


# ── Public API ───────────────────────────────────────────────────────────────

def send_booking_request_email(
    tenant_id: str,
    *,
    booking: dict[str, Any],
    room: dict[str, Any],
    pricing: dict[str, Any],
    property_data: dict[str, Any],
) -> None:
    """Fire-and-forget: send 'booking request received' email to the guest."""
    guest_email = (booking.get("guest_email") or "").strip()
    if not guest_email:
        return

    property_name = property_data.get("name", "AIR BEE Property")
    subject = f"Booking Request Received — {property_name}"
    body = _pending_email_body(booking, room, pricing, property_data)
    html = _build_email_html(
        subject_line=subject,
        property_name=property_name,
        body_html=body,
        contact_email=property_data.get("contact_email", ""),
        contact_phone=property_data.get("contact_phone", ""),
    )

    bcc = [ADMIN_NOTIFY_EMAIL] if ADMIN_NOTIFY_EMAIL else []
    sent = _send_ses(to_email=guest_email, subject=subject, html_body=html, bcc_emails=bcc)
    _log_email(tenant_id, to_email=guest_email, email_type="booking_request", subject=subject, status="sent" if sent else "failed")


def send_booking_confirmed_email(
    tenant_id: str,
    *,
    booking: dict[str, Any],
    room_name: str,
    property_data: dict[str, Any],
) -> None:
    """Fire-and-forget: send 'booking confirmed' email to the guest."""
    guest_email = (booking.get("guest_email") or "").strip()
    if not guest_email:
        return

    property_name = property_data.get("name", "AIR BEE Property")
    subject = f"Booking Confirmed — {property_name}"
    body = _confirmed_email_body(booking, room_name, property_data)
    html = _build_email_html(
        subject_line=subject,
        property_name=property_name,
        body_html=body,
        contact_email=property_data.get("contact_email", ""),
        contact_phone=property_data.get("contact_phone", ""),
    )

    sent = _send_ses(to_email=guest_email, subject=subject, html_body=html)
    _log_email(tenant_id, to_email=guest_email, email_type="booking_confirmed", subject=subject, status="sent" if sent else "failed")
