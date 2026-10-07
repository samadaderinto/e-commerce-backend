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
| 🏗️ **[Infrastructure & Deployment](infrastructure.md)** | Docker Compose, Postgres, Redis, MinIO, Elasticsearch, and HostGator production deployment. | DevOps / SRE |
| 📊 **[Observability & Monitoring](observability.md)** | Prometheus metrics, Grafana dashboards, Loki log streaming, Tempo tracing, and Silk profiling. | DevOps / SRE |
| 🔍 **[System Audit & Findings](system-audit-2026-10-06.md)** | Historic bug audits, gap analyses, and architectural resolutions. | Technical Leads |

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

# 3. Apply database migrations & seed realistic demo accounts
.venv/bin/python server/manage.py migrate
.venv/bin/python server/manage.py seed_demo --password 'ProaceDemo2026!'

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

---

## 🧪 Verification Commands

Always run these suites before committing changes:

```bash
# Frontend Type Checking & Unit Tests
npm run typecheck
npm run test:unit

# Backend Tests (Full suite: 184 tests)
.venv/bin/pytest server/
```
