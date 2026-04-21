# AIR BEE Frontend

React + Vite frontend for AIR BEE, an AI-powered hospitality operations platform.

## Requirements

- Node.js 18+
- npm 9+

## Local development

```sh
npm install
npm run dev
```

Separate frontend targets:

```sh
npm run dev:platform
npm run dev:booking
```

## Build

```sh
npm run build
npm run preview
```

Dedicated builds for split AWS hosting:

```sh
npm run build:platform
npm run build:booking
```

## Environment variables

Create `frontend/.env.local` with:

```env
VITE_COGNITO_USER_POOL_ID=...
VITE_COGNITO_CLIENT_ID=...
VITE_API_URL=https://<api-id>.execute-api.ap-south-1.amazonaws.com
VITE_APP_HOSTING_MODE=unified
```

For S3 + CloudFront hosting, leave `VITE_API_URL` blank so the app uses same-origin `/api`, `/ai`, and `/public` routes.

## Deployment

Use separate Amplify apps when you want independent AWS hosting for the platform and public booking site.

- Legacy unified hosting: [amplify.yml](/f:/Airbee/amplify.yml)
- Platform/admin hosting: [amplify-platform.yml](/f:/Airbee/amplify-platform.yml)
- Booking-site hosting: [amplify-booking.yml](/f:/Airbee/amplify-booking.yml)

If you also split the backend, deploy separate platform and booking API Gateway endpoints with [ensure-split-backend.ps1](/f:/Airbee/scripts/ensure-split-backend.ps1). That script can generate `frontend/.env.platform.local` and `frontend/.env.booking.local`, and [ensure-amplify-split-hosting.ps1](/f:/Airbee/scripts/ensure-amplify-split-hosting.ps1) accepts separate `-PlatformApiUrl` and `-BookingApiUrl` values.

For lower-cost static hosting, use [ensure-s3-cloudfront-lambda-hosting.ps1](/f:/Airbee/scripts/ensure-s3-cloudfront-lambda-hosting.ps1). It builds the two frontend targets, creates Lambda Function URLs, provisions S3 + CloudFront, and routes `/api`, `/ai`, and `/public` through CloudFront using same-origin requests.
