# Architecture

## Overview

```mermaid
flowchart TB
  subgraph Clients["Flutter apps (web on Vercel, Android APKs)"]
    U[user_app<br/>resident / visitor]
    O[owner_app<br/>slot owner]
    A[admin_app<br/>society admin]
    G[guard_app<br/>gate guard]
    S[super_admin_app<br/>platform admin]
  end
  Clients -->|REST + JWT| API
  subgraph API["Django + DRF (Render)"]
    V[views: thin, permission per role]
    SV[services.py: bookings, pricing,<br/>payments, refunds, penalties, QR]
    V --> SV
  end
  SV --> DB[(PostgreSQL<br/>Supabase)]
  SV --> RD[(Redis<br/>Upstash)]
  W[Celery worker + beat] --> DB
  W --> RD
  SV -->|checkout, refunds| ST[Stripe]
  SV -->|orders, refunds| RZ[Razorpay]
  ST -->|signed webhook| V
  RZ -->|signed webhook| V
```

The five apps share one Dart package, `mobile/packages/core`: API client and endpoints, models
(`json_serializable`), the auth bloc and secure token storage, theme, common widgets, and the
`setupCoreDependencies` bootstrap. The API origin is a compile-time value
(`--dart-define=API_BASE_URL`), so the same code runs against localhost, staging or production.

## Backend layout

| App | Responsibility |
|---|---|
| `accounts` | User (roles: user, society_admin, guard, super_admin), vehicles, notifications, JWT login, guard credentials, role permissions |
| `societies` | Societies, parking slots (society or resident owned, approval workflow), availability windows, search and geocoding |
| `bookings` | Booking model, **state machine**, **pricing**, availability and booking services, Celery tasks (expiry, no-show) |
| `payments` | Stripe and Razorpay checkout/orders, idempotent webhooks, capture, refunds, `PaymentEvent` audit log |
| `penalties` | Overstay penalty calculation and creation |
| `qr_validation` | Signed QR tokens, entry/exit validation, `ScanEvent` log |
| `admin_api` | Dashboards, refund lookup and refund endpoints, demo seed/reset |

Views stay thin: they validate input, check the role and call a function in `services.py`. Business rules
(and the transactions and row locks that protect them) live in services so they can be unit tested without HTTP.

## Roles

| Role | Can do |
|---|---|
| Resident / visitor (`user`) | Search, book, pay, view QR, cancel, pay penalties, manage vehicles; may also list their own slot (owner) |
| Society admin | Approve residents and slots, manage slots and availability windows, add guards, see society bookings |
| Guard | Scan entry and exit for their own society, only if granted scan rights |
| Super admin | Onboard societies, platform dashboard, look up bookings and issue full or partial refunds |

## Booking and payment flow

```mermaid
sequenceDiagram
  participant R as Resident app
  participant API as Django API
  participant DB as PostgreSQL
  participant ST as Stripe / Razorpay
  participant G as Guard app
  R->>API: POST /bookings (slot, vehicle, window)
  API->>DB: lock slot row, check availability, price with surge
  API-->>R: booking (pending_payment, 5 min lock)
  R->>API: POST /payments/initiate
  API->>ST: create checkout session / order
  R->>ST: pay (test card)
  ST-->>API: signed webhook (deduplicated by event id)
  API->>DB: capture payment, booking -> confirmed, slot reserved
  R->>API: GET /bookings/{id}/qr
  G->>API: POST /qr/entry (token)
  API->>DB: booking -> active, ScanEvent(approved)
  G->>API: POST /qr/exit (token)
  API->>DB: booking -> completed, penalty if late (same transaction)
```

## Booking states

```mermaid
stateDiagram-v2
  [*] --> pending_payment
  pending_payment --> confirmed: payment captured
  pending_payment --> expired: lock expired
  pending_payment --> cancelled: user cancels
  expired --> confirmed: late payment, slot still free
  confirmed --> active: gate entry
  confirmed --> cancelled
  confirmed --> no_show: past halfway, no entry
  active --> completed: gate exit
  confirmed --> partially_refunded
  active --> partially_refunded
  completed --> partially_refunded
  partially_refunded --> cancelled: refunded in full
  completed --> cancelled: full refund
  no_show --> cancelled: full refund
```

## Data model (main tables)

`User` → `Vehicle`; `Society` → `ParkingSlot` → `SlotAvailabilityWindow`; `Booking` (user, vehicle, slot) →
`Payment` → `Refund`; `Booking` → `Penalty` (one per booking, enforced by the database);
`Booking` → `ScanEvent`; `PaymentEvent` stores each webhook delivery under a unique `(provider, event_id)`.

## Time

All timestamps are stored in UTC. Availability windows are wall-clock times in the project zone
(Asia/Kolkata), and apps display IST. Window checks convert to local time and split at midnight.

Deployment and free-tier limits: [DEPLOYMENT.md](DEPLOYMENT.md). Failure modes and tests: [EDGE_CASES.md](EDGE_CASES.md).
