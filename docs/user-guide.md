# AIR BEE — User Guide

**Your hotel management dashboard at `dashboard.ascendersservices.in`**

---

## Table of Contents

1. [Logging In](#1-logging-in)
2. [Dashboard](#2-dashboard)
3. [Bookings](#3-bookings)
4. [Booking Calendar](#4-booking-calendar)
5. [Rooms](#5-rooms)
6. [Guests](#6-guests)
7. [Payments & Invoices](#7-payments--invoices)
8. [Pricing Rules](#8-pricing-rules)
9. [Housekeeping](#9-housekeeping)
10. [Maintenance](#10-maintenance)
11. [Expenses](#11-expenses)
12. [Staff Management](#12-staff-management)
13. [Reports](#13-reports)
14. [Audit Log](#14-audit-log)
15. [Settings](#15-settings)
16. [Public Booking Site](#16-public-booking-site)
17. [Guest Portal](#17-guest-portal)
18. [Email Notifications](#18-email-notifications)

---

## 1. Logging In

1. Go to **`https://dashboard.ascendersservices.in`**
2. Click **Sign In**
3. Enter your email and password
4. You will land on the main Dashboard

**Default credentials:**
- Email: `test@airbee.com`
- Password: `Test1234!`

> To add more users, go to AWS Cognito → User Pool → Create User.

---

## 2. Dashboard

The Dashboard is your home screen showing a live overview of the property.

### What you see

**Top KPI cards:**
- **Occupancy Rate** — Percentage of rooms occupied this month
- **Active Bookings** — Number of pending + confirmed reservations right now
- **Monthly Revenue** — Total revenue billed this month
- **Total Guests** — Number of guest profiles in your system

**Alert cards** (appear when action needed):
- **Outstanding Payments** — Total unpaid amount across all bookings
- **Dirty Rooms** — Number of rooms needing cleaning

**Charts:**
- **Revenue Trend** — Last 6 months of revenue as an area chart
- **Occupancy Trend** — Last 6 months of occupancy as a bar chart

**AI Intelligence Suite** — Quick links to AI-powered features (Copilot, Forecasting, Pricing, Guest Intelligence).

**AI Daily Briefing** — Click the button to get an AI-generated summary of today's property status.

---

## 3. Bookings

**Path:** Dashboard → Bookings (sidebar)

This is where you manage all reservations.

### Viewing Bookings

The table shows every booking with:
- Guest name and email
- Room assigned
- Check-in and check-out dates
- Total amount
- Booking status (colour-coded)
- Payment status (colour-coded)

### Changing Booking Status

Click the **status badge** in the Status column to get a dropdown:
- **Pending** — Reservation received, not yet confirmed
- **Confirmed** — You've confirmed the guest is coming (triggers confirmation email to guest)
- **Completed** — Guest has checked out
- **Cancelled** — Booking was cancelled

### Changing Payment Status

Click the **payment badge** in the Payment column:
- **Unpaid** — No payment received
- **Partial** — Partial payment received
- **Paid** — Fully settled

### Creating a Booking (Admin)

Use this when a guest calls or walks in directly.

1. Click **New Booking** (top right)
2. Fill in:
   - Guest name (required)
   - Email and phone (optional but recommended for emails)
   - Select a room from the dropdown
   - Check-in and check-out dates
   - Number of guests
   - Total amount (auto-calculated from room price × nights)
3. Click **Create Booking**

> **Note:** Booking status will be `pending` by default. Change it to `confirmed` once ready — this triggers the confirmation email.

---

## 4. Booking Calendar

**Path:** Dashboard → Calendar (sidebar)

A visual month-by-month calendar showing which rooms are occupied on which days.

### How to use

- **Navigate months** using the ← → arrows at the top
- **Rows** = each room in your property
- **Columns** = days of the month
- **Coloured blocks** = bookings (guest name shown on check-in day)

### Colour codes
| Colour | Status |
|--------|--------|
| Green | Confirmed |
| Yellow | Pending |
| Blue | Completed |
| Red | Cancelled |

Use this to quickly spot availability gaps, back-to-back bookings, or overlaps.

---

## 5. Rooms

**Path:** Dashboard → Rooms (sidebar)

Manage your room inventory — add rooms, update prices, change availability.

### Viewing Rooms

Rooms are shown as cards with:
- Room name and category
- Max guests capacity
- Nightly rate
- Status badge (Available / Maintenance / Unavailable)
- Housekeeping status badge

### Adding a Room

1. Click **Add Room**
2. Fill in:
   - **Room Name** (e.g., "Deluxe Suite 101")
   - **Category** (select from your room types)
   - **Max Guests** (capacity)
   - **Base Price** (per night in ₹)
   - **Base Occupancy** (guests included in base price; extra guests charged separately)
   - **Extra Guest Fee** (per person per night beyond base occupancy)
   - **Minimum Stay** (in nights)
   - **Check-in / Check-out Time** (e.g., "14:00", "11:00")
   - **Cancellation Policy** (shown to guests on the booking site)
   - **Status** (Available, Maintenance, Unavailable)
   - **Description and amenities**
3. Click **Save Room**

### Editing / Deleting a Room

Click the **pencil icon** to edit or **trash icon** to delete. A room with active bookings cannot be deleted.

### Demo Data

Click **Load Demo Data** to populate sample rooms and bookings for testing.

---

## 6. Guests

**Path:** Dashboard → Guests (sidebar)

Your guest database. Store profiles for repeat guests, VIPs, and contacts.

### Adding a Guest

1. Click **Add Guest**
2. Enter name, email, phone, and any notes
3. Click **Save**

### VIP Flag

Click the **star icon** next to any guest to toggle VIP status. VIP guests are visually highlighted.

### Guest Notes

Use the notes field to record preferences, dietary requirements, allergies, or any special requests.

---

## 7. Payments & Invoices

**Path:** Dashboard → Payments (sidebar)

Track money received and generate invoices for guests.

### Overview cards

- **Outstanding** — Total unpaid balance across all active bookings
- **Unpaid Bookings** — Count of bookings with outstanding balances
- **Invoices** — Total invoices generated

### Recording a Payment

When a guest pays (cash, card, UPI, etc.):

1. Find the booking in the Payments tab
2. Click **Record** button
3. Enter:
   - Amount received
   - Payment method (cash / card / bank transfer / UPI / cheque / other)
   - Payment date
   - Optional notes
4. Click **Record Payment**

The system automatically updates the booking's `amount_paid` and changes `payment_status` from unpaid → partial → paid.

> Previous payments for the same booking are shown in the dialog so you can see the payment history.

### Creating an Invoice

1. Find the booking in the Payments tab
2. Click **Invoice** button
3. An invoice is generated automatically with a sequential number (INV-0001, INV-0002, etc.)

### Viewing Invoices

Switch to the **Invoices** tab to see all generated invoices with status, amount, issue date, and due date.

---

## 8. Pricing Rules

**Path:** Dashboard → Pricing Rules (sidebar)

Set dynamic pricing that automatically adjusts room rates based on season, day of week, or minimum stay.

### Rule Types

| Type | Use case |
|------|---------|
| **Seasonal** | Higher rates in peak season (e.g., Dec–Jan) |
| **Weekend** | Surcharge on Fridays and Saturdays |
| **Holiday** | Special rates for festivals / holidays |
| **Last Minute** | Discount for bookings within 3 days |
| **Early Bird** | Discount for advance bookings |
| **Minimum Stay** | Enforce minimum stay during peak period |

### Adding a Rule

1. Click **New Rule**
2. Fill in:
   - **Rule Name** (e.g., "Christmas Week Surcharge")
   - **Rule Type**
   - **Room** — Leave blank to apply to all rooms, or select a specific room
   - **Adjustment Type** — Percentage or Fixed amount
   - **Value** — Use positive numbers for surcharge (e.g., `20` = 20% more), negative for discount (e.g., `-10` = 10% off)
   - **Start / End Date** — Leave blank for "always active"
   - **Min Nights** — Minimum stay required for rule to apply
   - **Priority** — Lower number = applied first when multiple rules match
   - **Active** — Toggle to enable/disable without deleting
3. Click **Create Rule**

### Managing Rules

Toggle the **Active** switch on the table to quickly enable or disable a rule without opening it. Click the pencil to edit or trash to delete.

---

## 9. Housekeeping

**Path:** Dashboard → Housekeeping (sidebar)

Track which rooms are clean, dirty, or being cleaned right now.

### Room Cards

Each room card shows:
- Room name
- Current housekeeping status with icon

### Status Flow

| Status | Meaning | Next Action |
|--------|---------|-------------|
| **Clean** | Ready for guest | — |
| **Dirty** | Needs cleaning (guest checked out) | Click "Start Cleaning" |
| **In Progress** | Currently being cleaned | Click "Ready for Inspection" |
| **Inspecting** | Supervisor checking | Click "Mark Clean" |

Click the action button on each card to advance to the next status.

### Tip

After a guest checks out, change the booking status to "Completed" in Bookings, then go to Housekeeping and mark that room as dirty so your housekeeping team knows to clean it.

---

## 10. Maintenance

**Path:** Dashboard → Maintenance (sidebar)

Log and track repair requests and issues across the property.

### Overview

- **Open Requests** — Count of unresolved issues
- **Urgent** — Count of high-priority requests needing immediate attention

### Filtering

Use the status filter buttons at the top to view:
- All requests
- Open only
- In Progress
- Resolved
- Closed

### Creating a Request

1. Click **New Request**
2. Fill in:
   - **Title** (e.g., "AC not cooling in Room 201")
   - **Room** (optional — select the affected room)
   - **Priority** — Low / Normal / High / Urgent
   - **Description** — Details of the issue
   - **Reported By** — Staff member name
3. Click **Create**

### Updating Status

In the table, use the **status dropdown** on each row to move a request through:
`Open` → `In Progress` → `Resolved` → `Closed`

The system automatically records the resolution timestamp when you mark something as Resolved.

---

## 11. Expenses

**Path:** Dashboard → Expenses (sidebar)

Record all operating costs to track profitability.

### Viewing Expenses

Use the date range filters (**From** / **To**) and category filter to narrow down expenses. The page shows:
- Total expenses for the period
- Breakdown by top 5 categories
- Full expense list table

### Recording an Expense

1. Click **Add Expense**
2. Fill in:
   - **Date**
   - **Category** (utilities, salaries, maintenance, supplies, etc.)
   - **Description** (e.g., "Electricity bill - March")
   - **Amount**
   - **Payment Method**
   - **Vendor** (optional)
3. Click **Save**

### Categories Available

Utilities · Salaries · Maintenance · Supplies · Food & Beverage · Marketing · Laundry · Repairs · Insurance · Taxes · Rent · Other

### Tip

Expenses feed directly into the **Net Revenue** calculation in Reports (Total Revenue - Total Expenses = Net Revenue). Keep expenses up to date for accurate profitability tracking.

---

## 12. Staff Management

**Path:** Dashboard → Staff (sidebar)

Manage your team directory.

### Staff Cards by Role

At the top, count cards show how many active staff you have in each role:
Manager · Front Desk · Housekeeping · Maintenance · Staff

### Adding a Staff Member

1. Click **Add Staff**
2. Fill in:
   - **Full Name** (required)
   - **Role** (manager, front_desk, housekeeping, maintenance, staff)
   - **Department** (e.g., "Operations", "F&B")
   - **Email** and **Phone**
   - **Notes** (optional)
   - **Active** toggle
3. Click **Add Staff**

### Managing Staff

- Toggle the **Active** switch to mark staff as inactive without deleting them (useful for seasonal staff)
- Click pencil to edit details
- Click trash to permanently remove

---

## 13. Reports

**Path:** Dashboard → Reports (sidebar)

Your financial analytics hub with KPIs, charts, and compliance reports.

### Month Selector

Use the **month picker** at the top right to view any month's data.

### KPI Cards

| Metric | What it means |
|--------|--------------|
| **Occupancy Rate** | % of rooms occupied this month |
| **ADR** (Average Daily Rate) | Average revenue per occupied room night |
| **RevPAR** (Revenue Per Available Room) | Revenue efficiency including empty rooms |
| **Total Revenue** | All booking amounts for the month |
| **Collected** | Actual cash received (paid bookings) |
| **Outstanding** | Unpaid balances |
| **Expenses** | Total operating costs recorded |
| **Net Revenue** | Total Revenue minus Expenses |

### Report Tabs

**Overview**
- Daily Revenue bar chart showing revenue by day
- Booking Status Breakdown (count and value of pending/confirmed/completed/cancelled)

**GST Report**
- Line-by-line GST breakdown for each booking
- Columns: Guest, Room, Check-in, Check-out, Base Amount, GST, Service Charge, Total
- Summary totals row at the top
- Use this for your monthly GST filing

**By Source**
- Revenue breakdown by how bookings came in (online, direct, phone, etc.)
- Shows booking count and percentage of total revenue per source

### Exporting

Click **Export CSV** to download all bookings for the selected month as a spreadsheet. Use this for accounting or external reporting.

---

## 14. Audit Log

**Path:** Dashboard → Audit Log (sidebar)

A complete history of every change made in the system — who changed what and when.

### Filtering

Use the **Entity Type** dropdown to filter by:
- All
- Bookings
- Rooms
- Guests
- Payments
- Settings

### Reading the Log

Each entry shows:
- **Timestamp** — Exact date and time
- **Action** (colour-coded badge) — Created / Updated / Deleted / Status Changed
- **Entity** — What type of record and its ID
- **Changes** — Before and after values in JSON
- **IP Address** — Where the action came from

Use this to investigate disputes, track changes, or meet compliance requirements.

---

## 15. Settings

**Path:** Dashboard → Settings (sidebar, bottom)

Configure your property profile and booking site.

### Property Info

- **Property Name** — Shown on emails and the booking site
- **Subdomain** — Your property's subdomain on the platform
- **Custom Domain** — Your own domain for the booking site
- **Contact Email and Phone** — Shown to guests on the booking site and emails
- **Address** — Shown on confirmation emails and the guest portal
- **Currency** and **Timezone**

### Taxes & Charges

- **GST Enabled** — Toggle GST calculation on bookings
- **GST Percentage** — The GST rate (e.g., 12 for 12%)
- **GST Number** — Your registered GSTIN
- **Service Charge Enabled** — Toggle service charge
- **Service Charge Percentage** — The service charge rate

All taxes are calculated automatically on the public booking site when enabled.

### Booking Theme

Customise the look of your public booking page with brand colours and styles.

---

## 16. Public Booking Site

**URL:** `https://booking.ascendersservices.in`

This is the page your guests see when they want to book online. It is completely separate from your admin dashboard.

### How guests book

1. Guest visits `booking.ascendersservices.in`
2. Selects check-in date, check-out date, and number of guests
3. Available rooms appear with pricing (base rate + GST + service charge if enabled)
4. Guest clicks **Book Now** on their preferred room
5. Guest enters name, email, phone, and any notes
6. Booking is created as **Pending**
7. Guest receives an automatic confirmation email with booking details

### What appears on the booking page

- Property name and branding
- Room photos, description, max guests, amenities
- Nightly rate and total price breakdown
- Check-in/check-out times
- Cancellation policy
- Availability (rooms with conflicting confirmed/pending bookings are hidden)

### Tip

When a guest books online, you receive a **BCC email** (to `mohamedinsaf8.mi@gmail.com`) so you know immediately. You can then go to your dashboard, review the booking, and change the status to **Confirmed** — which sends the guest a second confirmation email.

---

## 17. Guest Portal

**URL:** `https://booking.ascendersservices.in/my-booking`

Guests can look up their own bookings without logging in.

### How it works

1. Guest goes to the Guest Portal URL
2. Enters the email address they used when booking
3. All their bookings appear showing:
   - Property name and address
   - Room name, check-in, check-out dates and times
   - Number of guests
   - Pricing breakdown (base, taxes, service charge, total)
   - Amount paid and balance due
   - Booking status and payment status
   - Cancellation policy
   - Property contact info (email and phone)

### Use cases

- Guest wants to check their check-in time
- Guest wants to see their invoice total
- Guest wants to find your property's address before arriving

---

## 18. Email Notifications

AIR BEE automatically sends emails for the following events:

### Guest receives email when:

| Event | Email sent |
|-------|-----------|
| New booking submitted online | "Booking Request Received" — includes room details, pricing, check-in info, guest portal link |
| Admin changes status to **Confirmed** | "Booking Confirmed" — includes reservation summary, property address, guest portal link |

### You receive email when:

Every time a guest submits a booking online, you receive the same "Booking Request Received" email as a **BCC** to `mohamedinsaf8.mi@gmail.com`. This lets you know immediately without logging in.

### Email details

- Sent **from:** `bookings@ascendersservices.in`
- Sent **to:** guest's email address
- **BCC on new bookings:** `mohamedinsaf8.mi@gmail.com`
- Styled with your property name, contact info, and a link to the guest portal

### If emails are not arriving

1. Check the guest email address is correct in the booking
2. Check AWS SES production access has been approved (AWS Console → SES → Account dashboard)
3. In sandbox mode, only verified email addresses can receive emails

---

## Quick Reference

### Booking Status Workflow
```
Guest books online
       ↓
   PENDING  ←─── You receive BCC email
       ↓
You review in dashboard
       ↓
  CONFIRMED  ←─── Guest receives confirmation email
       ↓
  Guest arrives + checks in
       ↓
  COMPLETED  ←─── Mark room as Dirty in Housekeeping
```

### Payment Workflow
```
Booking created (UNPAID)
       ↓
Guest pays (partial or full)
       ↓
Record in Payments tab
       ↓
Status auto-updates: UNPAID → PARTIAL → PAID
       ↓
Generate Invoice if needed
```

### Daily Operations Checklist

- [ ] Check Dashboard for new bookings (pending status)
- [ ] Confirm pending bookings → triggers guest emails
- [ ] Check Housekeeping — mark checked-out rooms as dirty
- [ ] Review Maintenance requests — action any urgent ones
- [ ] Record any payments received
- [ ] Check Notifications bell for alerts

### Keyboard Shortcuts (Admin Dashboard)

- Navigate using the **sidebar** on the left
- Use **Ctrl+Shift+R** to hard refresh if the page seems stale after a deployment

---

*AIR BEE — Hospitality Management Platform*  
*Support: bookings@ascendersservices.in*
