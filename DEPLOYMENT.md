# AIR BEE — AWS Deployment Guide

## Architecture
```
[Amplify] → [Cognito] + [API Gateway HTTP API] → [Lambda: airbee-backend (Django DRF)] → [RDS] + [Bedrock]
                                               ↑
                              [Lambda: airbee-cognito-trigger (Python)]
```
**Region:** us-east-1 (required for Bedrock Claude access)

For production you can keep the original single backend, or split it into a protected platform API and a public booking API that still share the same RDS database.

---

## Step 1 — Create RDS PostgreSQL

1. RDS Console → Create database
2. Engine: PostgreSQL 15 | Instance: db.t3.micro
3. DB name: `airbee`, Username: `airbee`, generate password
4. **Publicly accessible: YES** (for hackathon)
5. Security Group: allow port 5432 from 0.0.0.0/0 (restrict after demo)
6. Save: endpoint, port, username, password

**Run schema:**
```bash
psql -h <RDS_ENDPOINT> -U airbee -d airbee -f aws/database/schema.sql
```

---

## Step 2 — Create Cognito User Pool

1. Cognito Console → Create User Pool
2. Sign-in: Email | Self-registration: ON | Email verification: ON
3. Required attributes: `email`, `name`
4. Custom attributes: `custom:tenant_id` (String, mutable)
5. Create App Client: Type = Public, no secret
6. Note: **User Pool ID** + **App Client ID**

---

## Step 3 — Create IAM Role for Lambda

1. IAM Console → Roles → Create Role → Lambda
2. Attach policies:
   - `AWSLambdaBasicExecutionRole`
   - `AmazonBedrockFullAccess`
   - `AmazonCognitoPowerUser` (for cognito-trigger to update user attributes)
3. Name: `airbee-lambda-role`

---

## Step 4 — Enable Bedrock Model Access

1. Bedrock Console (us-east-1) → Model access
2. Request access to: **Claude 3.5 Haiku** (`anthropic.claude-3-5-haiku-20241022-v1:0`)
3. Wait for approval (usually instant for Haiku)

---

## Step 5 — Deploy Lambda Functions (2 total)

### 5a — airbee-backend (Django DRF — handles ALL API + AI routes)

```bash
cd aws/backend
pip install -r requirements.txt -t package/
cp -r airbee api lambda_handler.py package/
cd package && zip -r ../function.zip . && cd ..
```

In Lambda Console:
- Runtime: **Python 3.12**
- Handler: `lambda_handler.handler`
- Role: `airbee-lambda-role`
- Timeout: **60s**
- Memory: **512MB**

**Environment variables:**
```
DB_HOST=<rds-endpoint>
DB_PORT=5432
DB_NAME=airbee
DB_USER=airbee
DB_PASSWORD=<password>
COGNITO_USER_POOL_ID=<your-user-pool-id>
AWS_REGION=us-east-1
BEDROCK_REGION=us-east-1
DJANGO_SECRET_KEY=<any-random-string>
PUBLIC_BASE_DOMAIN=book.airbee.com
PUBLIC_CNAME_TARGET=<shared-booking-hostname>
PLATFORM_HOSTS=<comma-separated admin or marketing hosts>
AMPLIFY_APP_ID=<your-amplify-app-id>
AMPLIFY_BRANCH=main
AMPLIFY_REGION=ap-south-1
```

### 5b — airbee-cognito-trigger (Python)

```bash
cd aws/cognito-trigger-py
pip install -r requirements.txt -t package/
cp lambda_function.py package/
cd package && zip -r ../function.zip . && cd ..
```

In Lambda Console:
- Runtime: **Python 3.12**
- Handler: `lambda_function.handler`
- Role: `airbee-lambda-role`
- Timeout: **30s**
- Memory: **256MB**

**Environment variables:**
```
DB_HOST=<rds-endpoint>
DB_PORT=5432
DB_NAME=airbee
DB_USER=airbee
DB_PASSWORD=<password>
AWS_REGION=us-east-1
```

---

## Step 6 — Attach Cognito Trigger

1. Cognito Console → Your User Pool → User pool properties → Triggers
2. Post confirmation trigger → Select `airbee-cognito-trigger` Lambda

---

## Step 7 — Create API Gateway HTTP API

1. API Gateway Console → Create API → HTTP API
2. Add integration: `airbee-backend` Lambda
3. Add JWT Authorizer:
   - Issuer: `https://cognito-idp.us-east-1.amazonaws.com/<USER_POOL_ID>`
   - Audience: `<APP_CLIENT_ID>`

**Routes (both point to the single airbee-backend Lambda):**
```
ANY  /api/{proxy+}   → airbee-backend  [JWT auth]
ANY  /ai/{proxy+}    → airbee-backend  [JWT auth]
ANY  /public/{proxy+}→ airbee-backend  [no auth]
```

4. CORS: Origins `*`, Methods `*`, Headers: `Authorization, Content-Type`
5. Note the **API Gateway URL** (e.g., `https://abc123.execute-api.us-east-1.amazonaws.com`)

---

## Step 8 — Deploy Frontend on AWS Amplify

### 8a — Platform App Hosting

1. Amplify Console → New App → Host web app → GitHub
2. Select repo, branch: `insaf` (or `main`)
3. Build settings: use [amplify-platform.yml](/f:/Airbee/amplify-platform.yml)

**Environment variables in Amplify:**
```
VITE_COGNITO_USER_POOL_ID=us-east-1_XXXXXXXXX
VITE_COGNITO_CLIENT_ID=xxxxxxxxxxxxxxxxxxxxxxxxxx
VITE_API_URL=https://xxxxxxxxxx.execute-api.us-east-1.amazonaws.com
VITE_APP_HOSTING_MODE=platform
VITE_PLATFORM_HOSTS=app.airbee.com,admin.airbee.com
VITE_PUBLIC_BASE_DOMAIN=book.airbee.com
```

4. Attach your admin/marketing host, such as `app.airbee.com`

### 8b — Booking App Hosting

1. Create a second Amplify app from the same repo and branch
2. Build settings: use [amplify-booking.yml](/f:/Airbee/amplify-booking.yml)

**Environment variables in Amplify:**
```
VITE_API_URL=https://xxxxxxxxxx.execute-api.us-east-1.amazonaws.com
VITE_APP_HOSTING_MODE=booking
VITE_PUBLIC_BASE_DOMAIN=book.airbee.com
```

3. This app does not need Cognito frontend env vars unless you deliberately want auth pages there
4. Attach the public booking hosts and custom domains to this second Amplify app
5. Note both Amplify URLs separately

You can also bootstrap both Amplify apps from the CLI with:

```powershell
.\scripts\ensure-amplify-split-hosting.ps1 `
  -Repository <git-repo-url> `
  -BranchName main `
  -AccessToken <provider-access-token> `
  -PlatformApiUrl https://<platform-api-id>.execute-api.ap-south-1.amazonaws.com `
  -BookingApiUrl https://<booking-api-id>.execute-api.ap-south-1.amazonaws.com `
  -UserPoolId <cognito-user-pool-id> `
  -UserPoolClientId <cognito-client-id> `
  -PlatformHosts app.airbee.com,admin.airbee.com `
  -PublicBaseDomain book.airbee.com
```

## Split Backend Deployment

If you want separate AWS backends for the admin platform and the public booking site, keep the same database but deploy two Lambda and HTTP API Gateway targets from the same Django codebase:

- `airbee-platform-api` exposes `/api/*` and `/ai/*` with JWT auth
- `airbee-booking-api` exposes `/public/*` without auth

The backend code already supports this with `AIRBEE_API_SURFACE`. Use:

```powershell
.\scripts\ensure-split-backend.ps1 `
  -SourceLambdaName airbee-backend `
  -PlatformLambdaName airbee-platform-api `
  -BookingLambdaName airbee-booking-api `
  -PlatformApiName airbee-platform-api `
  -BookingApiName airbee-booking-api `
  -WriteFrontendEnvFiles
```

By default the script reads shared settings from `airbee-backend` and reuses its database, IAM role, Cognito pool, domain config, and Bedrock config. Pass overrides explicitly if you are bootstrapping without an existing unified backend.

When `-WriteFrontendEnvFiles` is enabled, it writes:

- `frontend/.env.platform.local`
- `frontend/.env.booking.local`

Then point split Amplify hosting at those two API URLs:

```powershell
.\scripts\ensure-amplify-split-hosting.ps1 `
  -Repository <git-repo-url> `
  -BranchName main `
  -AccessToken <provider-access-token> `
  -PlatformApiUrl https://<platform-api-id>.execute-api.ap-south-1.amazonaws.com `
  -BookingApiUrl https://<booking-api-id>.execute-api.ap-south-1.amazonaws.com `
  -UserPoolId <cognito-user-pool-id> `
  -UserPoolClientId <cognito-client-id> `
  -PlatformHosts app.airbee.com,admin.airbee.com `
  -PublicBaseDomain book.airbee.com
```

## S3 + CloudFront + Lambda Hosting

If you want the cheaper static-hosting path, keep the split Lambda backend and serve the frontend from S3 behind CloudFront instead of Amplify.

This repo now supports that flow with:

- [ensure-s3-cloudfront-lambda-hosting.ps1](/f:/Airbee/scripts/ensure-s3-cloudfront-lambda-hosting.ps1)
- [cloudfront-forward-host.js](/f:/Airbee/scripts/cloudfront-forward-host.js)
- [cloudfront-spa-rewrite.js](/f:/Airbee/scripts/cloudfront-spa-rewrite.js)

What the script does:

- ensures public Lambda Function URLs for `airbee-platform-api` and `airbee-booking-api`
- builds the `platform` and `booking` frontend targets with blank `VITE_API_URL` for same-origin routing
- creates private S3 buckets for the two frontend builds
- creates CloudFront distributions with:
  - default origin = S3 static build
  - `/api/*` and `/ai/*` routed to the platform Lambda Function URL
  - `/public/*` routed to the booking Lambda Function URL
- preserves the viewer host in `X-Forwarded-Host` so tenant host-based booking still works through CloudFront
- updates `PUBLIC_CNAME_TARGET` on the Lambda env so the existing DNS verification fallback points at the booking CloudFront target

Basic command:

```powershell
.\scripts\ensure-s3-cloudfront-lambda-hosting.ps1
```

With first-party domains:

```powershell
.\scripts\ensure-s3-cloudfront-lambda-hosting.ps1 `
  -PlatformAliases app.airbee.com `
  -BookingAliases book.airbee.com,*.book.airbee.com `
  -CertificateArn <acm-certificate-arn-in-us-east-1>
```

Notes:

- The ACM certificate for CloudFront aliases must be in `us-east-1`.
- For this path, leave `VITE_API_URL` blank at build time so the frontend uses same-origin routes through CloudFront.
- The wildcard booking alias is what allows tenant subdomains such as `hotel.book.airbee.com`.

---

## Backend File Structure

```
aws/
├── database/schema.sql             ← Run once on RDS
├── backend/                        ← Single Django Lambda (ALL routes)
│   ├── lambda_handler.py           ← Mangum entry point
│   ├── requirements.txt
│   ├── airbee/
│   │   ├── settings.py
│   │   ├── urls.py
│   │   └── asgi.py
│   └── api/
│       ├── auth.py                 ← Cognito JWT verification
│       ├── urls.py                 ← CRUD routes (/api/*)
│       ├── urls_ai.py              ← AI routes (/ai/*)
│       └── views/
│           ├── rooms.py
│           ├── bookings.py
│           ├── guests.py
│           ├── housekeeping.py
│           ├── settings_view.py
│           ├── dashboard.py
│           └── ai.py               ← All 7 AI endpoints (Bedrock)
└── cognito-trigger-py/             ← Signup trigger (separate Lambda)
    ├── lambda_function.py
    └── requirements.txt
```

---

## Verification Checklist

- [ ] Sign up with a new email
- [ ] Check email for verification code
- [ ] Enter code → lands on `/admin`
- [ ] Dashboard loads with stats (no errors in console)
- [ ] Click "Daily AI Briefing" → AI response appears
- [ ] Create a room → appears in room list
- [ ] Create a booking → appears in bookings table
- [ ] Open `/admin/settings` and confirm a platform booking URL is shown
- [ ] Add a custom domain CNAME to `PUBLIC_CNAME_TARGET`
- [ ] Click "Verify Custom Domain" and confirm status becomes `verified`
- [ ] Click Forecasting → Bedrock response renders charts
- [ ] Click AI Copilot → type a question → response appears

---

## Custom Domain Workflow

Use the dedicated booking Amplify app for all public booking hosts.

1. Set `PUBLIC_BASE_DOMAIN` on the backend to your tenant subdomain base, such as `book.airbee.com`.
2. Deploy the platform app with `VITE_APP_HOSTING_MODE=platform`.
3. Deploy the booking app with `VITE_APP_HOSTING_MODE=booking`.
4. Expose the booking base domain to the public booking app with `VITE_PUBLIC_BASE_DOMAIN`.
5. Keep your dashboard and marketing hosts in `PLATFORM_HOSTS` and `VITE_PLATFORM_HOSTS`.
6. If you want the app to manage certificates and DNS instructions through Amplify, also set:
   - `AMPLIFY_APP_ID`
   - `AMPLIFY_BRANCH`
   - `AMPLIFY_REGION`
7. Bootstrap the wildcard booking domain on the booking Amplify app:
```powershell
.\scripts\ensure-amplify-platform-domain.ps1 -AppId <app-id> -DomainName book.airbee.com -BranchName main
```
8. In the Settings screen, the operator can enter a custom domain like `stay.hotelname.com` and click `Sync Custom Domain`.
9. When Amplify mode is enabled, the app will create or update the domain association and surface the exact DNS records required for:
   - certificate validation
   - application routing
10. If the operator clears or changes the custom domain and saves settings, the app deprovisions the previous Amplify custom-domain mapping before keeping the tenant on the new domain or the platform subdomain.
11. When Amplify mode is not enabled, the app falls back to the shared-CNAME verifier using `PUBLIC_CNAME_TARGET`.
12. Until the domain is fully provisioned, the tenant continues using the platform subdomain.

---

## Quick Debug

**Lambda not connecting to RDS?**
- Check security group allows Lambda IP (or 0.0.0.0/0 for hackathon)
- Verify DB_HOST is the full RDS endpoint

**Bedrock `AccessDeniedException`?**
- Enable model access in Bedrock console
- Verify Lambda IAM role has `bedrock:InvokeModel` permission

**CORS errors in browser?**
- Verify API Gateway CORS is configured
- `django-cors-headers` handles it inside Django too (`CORS_ALLOW_ALL_ORIGINS = True`)

**Cognito trigger not firing?**
- Verify trigger is attached in Cognito User Pool → Triggers
- Check Lambda CloudWatch logs for errors

**401 Unauthorized from API?**
- Ensure `COGNITO_USER_POOL_ID` env var is set on `airbee-backend` Lambda
- Check the JWT Authorizer issuer URL matches your User Pool ID exactly
