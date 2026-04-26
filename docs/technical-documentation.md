# AIR BEE — Technical Documentation

**Platform:** Hospitality Management System  
**Stack:** Python/Django (Lambda) · React/TypeScript (CloudFront/S3) · PostgreSQL (Supabase) · AWS SES  
**Version:** April 2026

---

## Architecture Overview

```
Guest Browser
    │
    ├── booking.ascendersservices.in  ──► CloudFront (E23MH1U2RG8SWS)
    │                                         │
    └── dashboard.ascendersservices.in ──► CloudFront (EIH3378NUD87F)
                                              │
                                         S3 Bucket (airbee-frontend-132334512551)
                                         React SPA (same bundle, routes by hostname)

Admin Browser                          API Gateway (fu6frsnvui — unified)
    │                                         │
    └── /admin/* ────────────────────────────►├── /api/* ──► Lambda: airbee-platform-api
                                              │               (JWT auth via Cognito)
                                              └── /public/* ──► Lambda: airbee-booking-api
                                                                 (no auth required)
```

### Key Infrastructure
| Resource | ID / Value |
|----------|------------|
| AWS Region | ap-south-1 (Mumbai) |
| Cognito User Pool | ap-south-1_XaPmqKaR4 |
| Cognito Client | 3cpce14mrt8c041l6epv4tiv2k |
| Platform API Gateway | 3iy51exnql |
| Booking API Gateway | imj4k6lnze |
| Unified API Gateway | fu6frsnvui |
| S3 Bucket | airbee-frontend-132334512551 |
| CloudFront (booking) | E23MH1U2RG8SWS → d1yw21sr8485y1.cloudfront.net |
| CloudFront (dashboard) | EIH3378NUD87F → d2ski8nitudjya.cloudfront.net |
| Database | Supabase PostgreSQL (aws-1-ap-south-1.pooler.supabase.com) |
| SES Region | ap-south-1 |
| SES Sender | bookings@ascendersservices.in |

### Authentication
- **Admin routes** use AWS Cognito JWT tokens. The `CognitoAuthentication` middleware (api/auth.py) validates the token from the `Authorization: Bearer <token>` header.
- `custom:tenant_id` claim in the JWT determines which property's data is returned.
- **Public routes** (`/public/*`) use `AllowAny` permission — no token required.
- Localhost falls through to a local dev bypass returning a fixed test tenant.

### Multi-tenancy
Every database table has a `tenant_id` column (UUID). All queries filter by `tenant_id` from the authenticated user's JWT claim. A single deployment serves multiple properties with complete data isolation.

---

## Backend Modules

### 1. bookings.py — Admin Booking Management
**Endpoints:** Authenticated (`/api/bookings`, `/api/bookings/{id}`)

#### Classes

**`BookingList`**
- `GET /api/bookings` — Returns all bookings for the tenant joined with room name and base price. Ordered by `created_at DESC`.
- `POST /api/bookings` — Creates a new booking from the admin dashboard.
  - Validates room exists and belongs to tenant (with `FOR UPDATE` lock)
  - Checks room status is `available`
  - Validates guest count ≤ max_guests
  - Validates guest_id exists if provided
  - For pending/confirmed status: checks no overlapping bookings exist
  - Auto-calculates `total_amount = base_price × nights` if not provided

**`BookingDetail`**
- `PUT /api/bookings/{booking_id}` — Updates a booking's status, payment_status, amount_paid, or notes.
  - Uses `COALESCE` so only provided fields are updated
  - When `status = "confirmed"`: fetches room name and property data, then calls `send_booking_confirmed_email()` (best-effort, never raises)

#### Helper Functions
| Function | Purpose |
|----------|---------|
| `_serialize(row, columns)` | Converts DB row to dict; UUIDs → str, Decimals → float, dates → ISO string |
| `_parse_date(raw)` | Parses `YYYY-MM-DD` string to `date` object |
| `_safe_int(value, default)` | Type-safe integer conversion |
| `_safe_float(value, default)` | Type-safe float conversion |
| `_normalize_uuid(raw)` | Validates and normalizes UUID strings |

#### Constants
```python
ALLOWED_BOOKING_STATUS = {"pending", "confirmed", "cancelled", "completed"}
ALLOWED_PAYMENT_STATUS = {"unpaid", "partial", "paid"}
```

---

### 2. public_booking.py — Public Guest Booking
**Endpoints:** No auth required (`/public/*`)

#### Classes

**`PublicPropertyView`**
- `GET /public/properties/{slug}` — Fetch property info by slug. Accepts `?check_in`, `?check_out`, `?guests` query params. Returns property details + available rooms + per-room pricing.

**`PublicSiteView`**
- `GET /public/site` — Same as above but resolves the property from the HTTP `Host` header. Used when a tenant has a custom domain.

**`PublicBookingCreateView`**
- `POST /public/properties/{slug}/bookings` — Create a guest booking via slug.

**`PublicSiteBookingCreateView`**
- `POST /public/site/bookings` — Create a guest booking via host resolution.

**`PublicBookingLookup`**
- `GET /public/booking-lookup?email=&booking_id=` — Returns up to 10 bookings for the given email. Used by the guest self-service portal.

#### Key Functions

**`_get_property_by_slug(slug)`**
Queries `tenants` table by `slug` column. Returns serialized property dict or `None`.

**`_get_property_by_host(host)`**
Resolves a property from HTTP Host header using priority:
1. Custom domain (verified) — highest priority
2. Primary hostname
3. Subdomain label on `PUBLIC_BASE_DOMAIN`

**`_calculate_pricing(property_data, room, guests, nights)`**
```
base_amount       = base_price × nights
extra_guest_total = extra_guest_fee × max(0, guests - base_occupancy) × nights
subtotal          = base_amount + extra_guest_total
tax_amount        = subtotal × (gst_percentage / 100)   [if gst_enabled]
service_charge    = subtotal × (service_percentage / 100) [if service_charge_enabled]
total_amount      = subtotal + tax_amount + service_charge
```

**`_fetch_rooms(tenant_id, check_in, check_out, guests)`**
Queries available rooms. When dates provided, excludes rooms with overlapping `pending` or `confirmed` bookings using a correlated `NOT EXISTS` subquery.

**`_create_booking(property_data, request)`**
Full booking creation flow:
1. Validates required fields
2. Locks room row with `SELECT FOR UPDATE`
3. Validates room status, guest count, minimum_stay
4. Checks for booking conflicts
5. Calculates pricing
6. INSERTs booking as `pending` / `unpaid`
7. Creates notification (best-effort)
8. Sends guest email (best-effort, **outside** transaction)

---

### 3. email_utils.py — AWS SES Email
**Not a view — utility module imported by other views.**

#### Environment Variables
| Variable | Default | Purpose |
|----------|---------|---------|
| `SES_REGION` | `ap-south-1` | AWS region for SES client |
| `SES_FROM_EMAIL` | `bookings@ascendersservices.in` | Sender address |
| `SES_ENABLED` | `true` | Toggle email sending |
| `ADMIN_NOTIFY_EMAIL` | `mohamedinsaf8.mi@gmail.com` | BCC on every booking request |

#### Functions

**`_fmt_currency(amount, currency)`**
Formats `amount` as `₹1,234` (INR) or `USD 1,234.56` for other currencies.

**`_fmt_date(raw)`**
Converts any date/ISO string to `"26 April 2026"` format.

**`_send_ses(*, to_email, subject, html_body, from_email, bcc_emails)`**
Creates a `boto3` SES client and calls `send_email`. Catches `ClientError` (logs warning) and all other exceptions. Returns `bool` (sent or not). Never raises.

**`_log_email(tenant_id, *, to_email, email_type, subject, status)`**
Inserts a row into `email_logs` table. Silently ignores failures.

**`send_booking_request_email(tenant_id, *, booking, room, pricing, property_data)`**
Sends the "Booking Request Received" email to the guest. BCCs `ADMIN_NOTIFY_EMAIL`. Called after booking INSERT commits.

**`send_booking_confirmed_email(tenant_id, *, booking, room_name, property_data)`**
Sends the "Booking Confirmed" email to the guest. Called when admin changes booking status to `confirmed`.

#### Email Templates
Both emails use a shared HTML wrapper with:
- Forest green gradient header (`#1a3a2a` → `#2d5a3d`)
- Gold accent text (`#d4b483`)
- Max-width 600px responsive layout
- Property name, contact email/phone in footer

---

### 4. payments.py — Payments & Invoicing
**Endpoints:** Authenticated

#### Classes

**`BookingPaymentList`**
- `GET /api/bookings/{booking_id}/payments` — List all payments for a booking.
- `POST /api/bookings/{booking_id}/payments` — Record a payment.
  - Updates `bookings.amount_paid` by summing all payments
  - Auto-updates `payment_status`: `unpaid` → `partial` → `paid` based on total paid vs total amount

**`InvoiceList`**
- `GET /api/invoices` — List all invoices joined with booking and guest data.
- `POST /api/invoices` — Create an invoice for a booking.
  - Auto-generates invoice number: `INV-XXXX` (sequential per tenant)
  - Sets amount from booking's `total_amount`

**`InvoiceDetail`**
- `GET /api/invoices/{invoice_id}` — Get invoice with full booking details.
- `PUT /api/invoices/{invoice_id}` — Update invoice status, due_date, or notes.

#### Allowed Payment Methods
`cash`, `card`, `bank_transfer`, `upi`, `cheque`, `other`

---

### 5. pricing_rules.py — Dynamic Pricing Rules
**Endpoints:** Authenticated

#### Classes

**`PricingRuleList`**
- `GET /api/pricing-rules` — List all rules. Filter by `?room_id=` to get room-specific rules. Returns rules joined with room name.
- `POST /api/pricing-rules` — Create a new rule.

**`PricingRuleDetail`**
- `PUT /api/pricing-rules/{rule_id}` — Update rule fields.
- `DELETE /api/pricing-rules/{rule_id}` — Delete rule.

#### Rule Fields
| Field | Type | Values |
|-------|------|--------|
| `rule_type` | text | seasonal, weekend, holiday, last_minute, early_bird, minimum_stay |
| `adjustment_type` | text | percentage, fixed |
| `adjustment_value` | decimal | Negative = discount, Positive = surcharge |
| `start_date` / `end_date` | date | Optional date range |
| `min_nights` | int | Minimum stay requirement |
| `priority` | int | Lower = higher priority |
| `is_active` | bool | Enable/disable without deleting |
| `room_id` | uuid | Null = applies to all rooms |

---

### 6. staff.py — Staff Management
**Endpoints:** Authenticated

#### Classes

**`StaffList`**
- `GET /api/staff` — List all staff ordered by name.
- `POST /api/staff` — Create staff member.

**`StaffDetail`**
- `PUT /api/staff/{staff_id}` — Update staff details or toggle `is_active`.
- `DELETE /api/staff/{staff_id}` — Remove staff member.

#### Roles
`manager`, `front_desk`, `housekeeping`, `maintenance`, `staff`

---

### 7. maintenance.py — Maintenance Requests
**Endpoints:** Authenticated

#### Classes

**`MaintenanceList`**
- `GET /api/maintenance` — List requests. Filter by `?status=` or `?priority=`.
- `POST /api/maintenance` — Create new request.

**`MaintenanceDetail`**
- `PUT /api/maintenance/{req_id}` — Update request. Auto-sets `resolved_at = NOW()` when status changes to `resolved`.
- `DELETE /api/maintenance/{req_id}` — Delete request.

#### Status Flow
`open` → `in_progress` → `resolved` → `closed`

#### Priority Levels
`low`, `normal`, `high`, `urgent`

---

### 8. expenses.py — Expense Tracking
**Endpoints:** Authenticated

#### Classes

**`ExpenseList`**
- `GET /api/expenses` — Returns expense list + summary dict keyed by category + total. Filter by `?from=`, `?to=`, `?category=`.
- `POST /api/expenses` — Record an expense.

**`ExpenseDetail`**
- `PUT /api/expenses/{expense_id}` — Update expense.
- `DELETE /api/expenses/{expense_id}` — Delete expense.

#### Categories
`utilities`, `salaries`, `maintenance`, `supplies`, `food_beverage`, `marketing`, `laundry`, `repairs`, `insurance`, `taxes`, `rent`, `other`

#### Response Shape
```json
{
  "expenses": [...],
  "summary": { "utilities": 5000, "salaries": 50000 },
  "total": 55000
}
```

---

### 9. reports.py — Financial Reporting
**Endpoints:** Authenticated

#### Classes

**`ReportsSummary`**
- `GET /api/reports/summary?month=YYYY-MM`
- Returns:
  - `kpis`: occupancy_rate, ADR, RevPAR, total_revenue, amount_collected, outstanding, expense_total, net_revenue, total_bookings, cancellations
  - `daily_revenue`: Array of `{date, revenue, bookings}` for each day in month
  - `revenue_by_source`: Grouped by booking_source
  - `status_breakdown`: Count and amount by booking status

**`GSTReport`**
- `GET /api/reports/gst?month=YYYY-MM`
- Returns per-booking GST detail: base_amount, tax_amount, service_charge, total_amount with totals row.

**`ExportBookings`**
- `GET /api/reports/export/bookings?from=YYYY-MM-DD&to=YYYY-MM-DD`
- Returns CSV file download with all booking fields.

#### KPI Formulas
```
occupancy_rate = (total_room_nights / total_available_nights) × 100
ADR            = total_revenue / total_room_nights
RevPAR         = total_revenue / total_available_nights
net_revenue    = total_revenue - expense_total
outstanding    = SUM(total_amount - amount_paid) WHERE payment_status != 'paid'
```

---

### 10. notifications.py — In-App Notifications
**Endpoints:** Authenticated

#### Classes

**`NotificationList`**
- `GET /api/notifications` — Returns up to 50 notifications + `unread_count`.

**`NotificationMarkRead`**
- `PUT /api/notifications/{notification_id}/read` — Mark single notification read.
- `PUT /api/notifications/all/read` — Mark all notifications read.

#### Utility Function
```python
create_notification(tenant_id, type, title, message, related_id=None, related_type=None)
```
Called from other views (e.g., after new booking is created) to push a notification. Best-effort — wrapped in try/except by callers.

---

### 11. audit_log.py — Audit Trail
**Endpoints:** Authenticated

#### Classes

**`AuditLogList`**
- `GET /api/audit-logs` — Returns up to 200 log entries. Filter by `?entity_type=`.

#### Utility Function
```python
log_action(tenant_id, user_id, action, entity_type, entity_id, old_value=None, new_value=None, ip_address=None)
```

#### Logged Actions
`created`, `updated`, `deleted`, `status_changed`, `payment_recorded`

#### Entity Types
`bookings`, `rooms`, `guests`, `payments`, `settings`

---

### 12. rooms.py — Room Management
**Endpoints:** Authenticated

- `GET /api/rooms` — List all rooms with category name.
- `POST /api/rooms` — Create room.
- `PUT /api/rooms/{room_id}` — Update room.
- `DELETE /api/rooms/{room_id}` — Delete room (only if no active bookings).

#### Key Fields
| Field | Type | Notes |
|-------|------|-------|
| `name` | text | Required |
| `base_price` | decimal | Per night |
| `max_guests` | int | Capacity |
| `base_occupancy` | int | Guests included in base price |
| `extra_guest_fee` | decimal | Per extra guest per night |
| `minimum_stay` | int | Minimum nights |
| `status` | enum | available, maintenance, unavailable |
| `housekeeping_status` | text | clean, dirty, in_progress, inspecting |
| `check_in_time` / `check_out_time` | text | e.g., "14:00", "11:00" |
| `cancellation_policy` | text | Shown to guests |

---

### 13. guests.py — Guest Profiles
**Endpoints:** Authenticated

- `GET /api/guests` — List all guest profiles.
- `POST /api/guests` — Create profile.
- `PUT /api/guests/{guest_id}` — Update profile (name, email, phone, is_vip, tags, notes).
- `DELETE /api/guests/{guest_id}` — Delete profile.

---

### 14. dashboard.py — Dashboard KPIs
**Endpoints:** Authenticated

- `GET /api/dashboard/stats` — Aggregates:
  - Total rooms
  - Active bookings (pending + confirmed)
  - Occupancy rate (current month)
  - Monthly revenue (last 6 months array)
  - Occupancy trend (last 6 months array)
  - Outstanding payments total
  - Dirty rooms count
  - Total guest profiles

---

### 15. housekeeping.py — Housekeeping Status
**Endpoints:** Authenticated

- `GET /api/housekeeping` — List rooms with housekeeping status.
- `PUT /api/housekeeping/{room_id}` — Update a room's `housekeeping_status`.

#### Status Values
`clean` → `dirty` → `in_progress` → `inspecting` → `clean`

---

### 16. settings_view.py — Property Settings & Domains
**Endpoints:** Authenticated

- `GET /api/settings` — Returns tenant config, domain setup info, user profile, room categories.
- `PUT /api/settings` — Update tenant fields: name, subdomain, custom domain, logo, contact, currency, GST config, service charge, booking theme.
- `POST /api/settings/domain/verify` — Trigger domain verification (Amplify or CNAME DNS check).
- `GET /api/settings/room-categories` — List room categories.

#### Domain Resolution Priority (for booking site)
1. Custom `domain` field (if `domain_status = verified`)
2. `primary_hostname` (e.g., `booking.ascendersservices.in`)
3. `subdomain.PUBLIC_BASE_DOMAIN`
4. `/book/{slug}` path on platform

---

## Frontend Routing

The single React bundle serves two different experiences based on hostname:

```typescript
// site-hosts.ts
isPlatformHost(host)  // true if host is in VITE_PLATFORM_HOSTS or localhost
shouldRenderPublicBookingAtRoot(host)  // true for booking domains, false for platform hosts
```

| Domain | Experience |
|--------|-----------|
| `dashboard.ascendersservices.in` | Admin dashboard (login → /admin/*) |
| `booking.ascendersservices.in` | Public booking site (guest-facing) |
| `localhost:8080` | Admin dashboard (dev default) |

### Admin Routes (`/admin/*`)
| Path | Component |
|------|-----------|
| `/admin` | Dashboard |
| `/admin/bookings` | Bookings |
| `/admin/calendar` | BookingCalendar |
| `/admin/rooms` | Rooms |
| `/admin/guests` | Guests |
| `/admin/payments` | Payments |
| `/admin/pricing-rules` | PricingRules |
| `/admin/staff` | StaffManagement |
| `/admin/maintenance` | Maintenance |
| `/admin/expenses` | Expenses |
| `/admin/reports` | Reports |
| `/admin/housekeeping` | Housekeeping |
| `/admin/audit-log` | AuditLog |
| `/admin/settings` | Settings |
| `/admin/ai-copilot` | AICopilot |
| `/admin/marketing` | Marketing |
| `/admin/messaging` | Messaging |
| `/admin/channels` | Channels |

### Public Routes
| Path | Component |
|------|-----------|
| `/` | PublicBooking (booking site root on booking domain) |
| `/book/{slug}` | PublicBooking (property by slug) |
| `/my-booking` | GuestPortal |
| `/login` | Auth |

---

## Deployment

### Backend Deploy
```bash
# Rebuild ZIP
cd f:\Airbee\aws\backend
python -c "import zipfile, os, pathlib; ..."  # See project deploy commands

# Deploy to both Lambdas
python -m awscli lambda update-function-code --function-name airbee-booking-api --zip-file fileb://function.zip
python -m awscli lambda update-function-code --function-name airbee-platform-api --zip-file fileb://function.zip
```

### Frontend Deploy
Push to `deploy` branch — GitHub Actions builds and uploads to S3, then invalidates both CloudFront distributions automatically.

### Database Migrations
```cmd
set PGPASSWORD=Airbee@@@!!
"C:\Program Files\PostgreSQL\18\bin\psql.exe" -h aws-1-ap-south-1.pooler.supabase.com -U postgres.dlvrgnslknfehtywtzyh -d postgres -f "migration.sql"
```

---

## Database Tables Reference

| Table | Purpose |
|-------|---------|
| `tenants` | Property/hotel profiles |
| `bookings` | All reservation records |
| `rooms` | Room inventory |
| `room_categories` | Room type groupings |
| `guest_profiles` | Guest directory |
| `booking_payments` | Individual payment transactions |
| `invoices` | Generated invoices |
| `room_pricing_rules` | Dynamic pricing rules |
| `staff_members` | Staff directory |
| `maintenance_requests` | Maintenance issue tracker |
| `expenses` | Operating expense records |
| `notifications` | In-app notification queue |
| `audit_logs` | Change history trail |
| `email_logs` | Email send history |
| `housekeeping_logs` | Cleaning activity log |

---

## Environment Variables (Lambda)

| Variable | Lambda | Purpose |
|----------|--------|---------|
| `DB_HOST` | Both | Supabase host |
| `DB_USER` | Both | DB username |
| `DB_PASSWORD` | Both | DB password |
| `DB_NAME` | Both | Database name |
| `COGNITO_USER_POOL_ID` | Platform | JWT validation |
| `AIRBEE_API_SURFACE` | Both | `platform` or `public` |
| `PLATFORM_HOSTS` | Both | Platform hostname list |
| `PUBLIC_BASE_DOMAIN` | Both | Base domain for subdomains |
| `SES_FROM_EMAIL` | Both | Email sender address |
| `SES_ENABLED` | Both | Toggle email sending |
| `SES_REGION` | Both | SES AWS region |
| `ADMIN_NOTIFY_EMAIL` | Both | BCC recipient for bookings |
