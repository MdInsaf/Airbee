# Airbee

A multi-tenant hotel operations and revenue management platform with AI-powered insights, a public booking engine, and full AWS-native deployment.

---

## What it does

Each property owner gets an isolated admin workspace to manage their hotel day-to-day:

- **Rooms & Bookings** — inventory, reservations, payment status
- **Guests** — profiles, history, segmentation
- **Housekeeping** — room status tracking and task assignment
- **Marketing** — contacts, segments, email campaigns, message templates
- **Channel Manager** — iCal sync with OTAs
- **Public Booking Engine** — guest-facing booking page per property (custom domain support)
- **AI Suite** — demand forecasting, dynamic pricing, guest intelligence, sentiment analysis, booking risk prediction, daily briefing, and a free-form AI copilot

---

## Stack

| Layer | Technology |
|---|---|
| Frontend | React 18 + TypeScript + Vite + Tailwind + shadcn/ui |
| Backend | Django 5 + Django REST Framework (Python 3.12) |
| Runtime | AWS Lambda via Mangum (ASGI adapter) |
| Database | PostgreSQL (AWS RDS or Supabase) |
| Auth | AWS Cognito (JWT) |
| AI/LLM | AWS Bedrock (Claude 3.5 Haiku) — OpenAI fallback for local dev |
| API | AWS API Gateway HTTP API |
| Frontend Hosting | AWS Amplify or S3 + CloudFront |

---

## Project Structure

```
├── frontend/                  # React SPA (Vite)
│   └── src/
│       ├── pages/
│       │   ├── admin/         # Authenticated admin pages
│       │   └── PublicBooking  # Guest-facing booking engine
│       ├── components/
│       ├── contexts/          # Auth state (Cognito)
│       └── lib/               # Utilities
│
├── aws/
│   ├── backend/               # Django REST API (Lambda-deployable)
│   │   └── api/
│   │       └── views/         # rooms, bookings, guests, ai, public_booking, ...
│   ├── database/
│   │   ├── schema.sql         # 14-table PostgreSQL schema
│   │   └── seed_local.sql     # Local dev seed data
│   └── cognito-trigger/       # Post-signup Lambda (provisions tenant)
│
├── scripts/                   # PowerShell deployment helpers
├── docker-compose.yml         # Local dev (Postgres + Django)
├── deploy.ps1                 # Full AWS deployment script
└── DEPLOYMENT.md              # Step-by-step AWS setup guide
```

---

## Running Locally

### With Docker (recommended)

```bash
docker-compose up -d
# Backend: http://localhost:8000
# Frontend: http://localhost:8080
```

### Manual

**1. Database**
```bash
psql -h localhost -U airbee -d airbee -f aws/database/schema.sql
psql -h localhost -U airbee -d airbee -f aws/database/seed_local.sql
```

**2. Backend**
```bash
cd aws/backend
pip install -r requirements.txt
LOCAL_DEV=true python manage.py runserver
```

**3. Frontend**
```bash
cd frontend
npm install
npm run dev          # unified mode (http://localhost:8080)
npm run dev:platform # admin only
npm run dev:booking  # public booking only
```

### Environment Variables

**Frontend** (create `frontend/.env.local`):
```
VITE_COGNITO_USER_POOL_ID=...
VITE_COGNITO_CLIENT_ID=...
VITE_API_URL=http://localhost:8000
VITE_APP_HOSTING_MODE=unified
VITE_LOCAL_DEV=true
```

**Backend**:
```
LOCAL_DEV=true
DB_HOST=localhost
DB_PORT=5432
DB_NAME=airbee
DB_USER=airbee
DB_PASSWORD=airbee123
OPENAI_API_KEY=...        # for AI features in local dev
DJANGO_SECRET_KEY=any-string
```

> When `LOCAL_DEV=true`, Cognito auth is bypassed and the backend uses OpenAI instead of AWS Bedrock.

---

## Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for the full AWS setup guide covering Cognito, RDS, Lambda, API Gateway, and Amplify.

Quick deploy (PowerShell):
```powershell
./deploy.ps1
```

---

## Database

14 core tables with multi-tenant isolation via `tenant_id` on every row:

`tenants` · `profiles` · `user_roles` · `rooms` · `room_categories` · `room_pricing_rules` · `bookings` · `guests` · `housekeeping` · `channels` · `marketing_contacts` · `marketing_segments` · `marketing_campaigns` · `message_templates`

---

## AI Features

All powered by AWS Bedrock (Claude 3.5 Haiku) in production, OpenAI in local dev:

- **Copilot** — free-form Q&A with property context
- **Forecasting** — demand prediction with charts
- **Dynamic Pricing** — repricing recommendations per room
- **Guest Intelligence** — scoring and segmentation
- **Sentiment Analysis** — review NLP
- **Booking Risk** — no-show / cancellation prediction
- **Daily Briefing** — auto-generated operational summary
