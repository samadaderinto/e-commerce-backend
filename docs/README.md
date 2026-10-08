# Proace Commerce — Centralized Engineering Documentation

Welcome to the centralized engineering documentation for Proace Commerce. This documentation hub is designed to allow any software engineer—whether a newcomer or an experienced contributor—to understand the architecture, run the system locally, debug issues, and ship code confidently.

---

## ⚡ Quick Navigation & Guide Index

| Guide | Description | Primary Audience |
| :--- | :--- | :--- |
| 🚀 **[Getting Started](getting-started.md)** | Step-by-step onboarding, prerequisites, local setup without Docker, seed scripts, and test suites. | All Engineers |
| 🏛️ **[Architecture & API Map](architecture.md)** | Monorepo layout, request flow, full API endpoint directory, and design decisions. | Full-stack / Backend / Frontend |
| 💻 **[Frontend Architecture](frontend.md)** | Next.js 15 App Router, React 19, API proxy, state management, components, and types. | Frontend Engineers |
| ⚙️ **[Backend Engineering](backend.md)** | Django modular monolith, domain apps, Celery, Postgres, Redis, Elasticsearch, and credential sync. | Backend Engineers |
| 🛡️ **[Access Control & Roles](access-control.md)** | Role hierarchy (Technical Admin vs. Business Admin vs. Staff vs. Customer), permissions matrix, and activation. | Security / Operations / Backend |
| 🎨 **[UI & Interactive Primitives](ui-and-events.md)** | Design tokens, responsive conventions, modals, CartSheet, WalletTopup, and SSE live events. | Frontend / Designers |
| 📦 **[Shipping & Carriers](shipping-integrations.md)** | USPS, UPS, FedEx, DHL live rates, OAuth tokens, and tracking links. | Logistics / Checkout |
| 🏗️ **[Infrastructure](infrastructure.md)** & **[HostGator Deployment](deployment.md)** | Docker Compose, Postgres, Redis, MinIO, Elasticsearch, and HostGator production deployment. | DevOps / SRE |
| 📊 **[Observability & Monitoring](observability.md)** | Prometheus metrics, Grafana dashboards, Loki log streaming, Tempo tracing, and Silk profiling. | DevOps / SRE |
| **[Bug Audit — 8 October 2026](bug-audit-2026-10-08.md)** | Confirmed financial/inventory defects, source-level findings, and verification limits. | Engineering / Security |
| 🔍 **[Security & Audit Remediation](security-audit-remediation.md)** | Security remediations, checkout compensation, and architectural resolutions. | Technical Leads |

---

## 🧭 Monorepo Structure

```text
e-commerce-backend/
├── client/                     # Next.js 15 frontend application (App Router, React 19)
│   ├── src/app/                # Dynamic route pages and same-origin API proxy (/api/*)
│   ├── src/components/         # Domain UI components (storefront, cart, account, merchant, admin)
│   ├── src/lib/                # Client API helpers (api.ts), types (types.ts), geo utilities
│   └── tests/                  # Unit tests, integration tests, and Playwright e2e suites
├── server/                     # Django REST Framework modular backend
│   ├── codematics/             # Core project configuration & active storefront_settings.py
│   ├── storefront/             # Integrated public API views, routers, and catalog endpoints
│   ├── core/                   # User identity, address, wallet, and auth credential sync
│   ├── store/                  # Merchant stores, products, escrow ledgers, and payouts
│   ├── cart/ & payment/        # Carts, multi-carrier quotes, Stripe sessions, and orders
│   ├── notification/           # Celery workers, push notifications, and live SSE streams
│   ├── staff/                  # Backoffice staff and administration endpoints
│   ├── observability/          # Prometheus metrics, health checks, and tracing middleware
│   └── compose.yaml            # Local development container stack
├── monitoring/                 # Observability container stack (Prometheus, Grafana, Loki, Tempo)
│   └── compose.yaml
└── docs/                       # Canonical centralized engineering documentation hub
```

---

## 🧑‍💻 How To Run the Project in 3 Minutes

A new engineer can launch the complete development environment **without Docker**:

```bash
# 1. Install frontend dependencies
npm ci

# 2. Create Python virtual environment & install backend packages
python3 -m venv .venv
.venv/bin/python -m pip install -r server/requirements.txt

# 3. Apply database migrations & seed realistic accounts and catalog
.venv/bin/python server/manage.py migrate
.venv/bin/python server/manage.py populate_fake_data --password 'ProaceDemo2026!'

# 4. Start Django API server (Terminal 1)
.venv/bin/python server/manage.py runserver 127.0.0.1:8000

# 5. Start Next.js Development Server (Terminal 2)
npm run dev
```

Visit **`http://localhost:3000`** in your browser. The frontend automatically proxies `/api/*` to the Django backend at `http://127.0.0.1:8000/api/v1/`.

---

## 🔑 Key Architectural Axioms Every Engineer Must Know

1. **API Authority**: Django is the single source of truth for business logic, pricing, inventory stock, and permission enforcement.
2. **Same-Origin Proxy**: The browser UI never communicates with Django directly. All calls go through `client/src/app/api/` which stores JWT tokens in secure, HTTP-only SameSite cookies.
3. **Role Separation**:
   - **Technical Super Admin (`is_superuser=True`)**: System owner. Changes to passwords automatically synchronize across Django, MinIO, and Grafana via `server/core/auth_sync.py`.
   - **Business Admin (`is_business_admin=True`)**: Operator admin. Can manage staff, approve stores, and review payouts. Strictly isolated from infrastructure passwords.
   - **Staff (`is_staff=True`)**: Backoffice operator. Audits orders, processes refunds, and manages official brand stores.
   - **Customer / Merchant**: Regular shopper or independent vendor managing their own store.
4. **7-Day Review Escrow**: Customer refunds are allowed within 7 days. Seller sales balances remain `in_review` before unlocking to `cleared_net` for payouts.
5. **Split-Tender & Store Credit**: Shoppers can combine their ProAce Wallet balance with Stripe card payments. Order cancellations credit the wallet balance immediately.
6. **Hybrid Multi-Jurisdiction Destination Sales Tax**: Destination statutory sales taxes are calculated locally via `payment.TaxJurisdiction` (with 5-decimal precision and municipal ZIP overrides) or via Stripe Tax, with immutable order snapshots and Next.js backoffice management at `/admin/taxes`.

---

## 🧪 Verification & Testing Hierarchy

The testing architecture is split into two clear tiers:

### Tier 1: Offline / Fast Verification (No Servers Required)
Run these commands locally for fast, offline verification on every code change:

```bash
# 1. Frontend TypeScript Validation (zero type errors)
npm run typecheck

# 2. Frontend Unit Tests (24 tests via Node native runner)
npm run test:unit

# 3. Backend Test Suite (Django / Pytest — 283 tests; 8 environment-dependent skips offline)
.venv/bin/pytest server/
```

### Tier 2: Integration & End-to-End (E2E) Suites
Playwright runs these against live services to ensure full system fidelity:

1. **Start Backend & Seed Data**:
   ```bash
   .venv/bin/python server/manage.py populate_fake_data
   .venv/bin/python server/manage.py runserver 127.0.0.1:8000
   ```
2. **Start Frontend Proxy**:
   ```bash
   npm run dev
   ```
3. **Execute Test Suites**:
   ```bash
   # Run API proxy integration tests
   npm run test:integration

   # Run full browser end-to-end tests (desktop & mobile)
   npm run test:e2e
   ```

**E2E Test Coverage Breakdown (`client/tests/`)**:
- `api.integration.spec.ts`: Next.js proxy routing, cookie parsing, and auth token forwarding.
- `commerce.spec.ts`: Customer shopping journey, options picker, cart management, and checkout.
- `merchant-store.spec.ts`: Merchant onboarding, store settings, product/variant creation, RFC 4180 CSV imports.
- `backoffice.spec.ts`: Staff/admin dashboards, store review, order audits, and user management.
- `self-purchase.spec.ts`: Validation preventing merchants from buying their own items.
- `variant-images.spec.ts`: Dynamic variant option selection and gallery synchronization.
- `ui-stability.spec.ts` & `theme.spec.ts`: Focus trapping in dialogs, responsive breakpoints, and theme switching.

