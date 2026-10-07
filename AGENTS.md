# ProAce Commerce — Global AI Agent Guidelines & Architecture Rules

This file is the single, canonical source of instructions and operational rules for all AI coding agents working across the repository.

---

## 1. Monorepo Architecture & Single Source of Truth

- **Monorepo Layout**:
  - `client/`: Next.js 15 App Router with React 19 and React Query. The browser UI **must only** communicate via the same-origin `/api/*` proxy route. Direct browser requests to the Django backend origin are strictly forbidden.
  - `server/`: Django REST Framework modular monolith. This is the **authoritative** single source of truth for all business rules, prices, stock limits, user ownership, and access controls.
  - `docs/`: **Canonical Documentation Directory**.
  - `README.md` (root): **Primary Repository Entry Point & Overview**.
- **Documentation Rules**:
  - **All READMEs Except Root in `docs/`**: All documentation and README files—**with the sole exception of the root `README.md`**—must reside exclusively within `docs/` (e.g., `docs/README.md`, `docs/architecture.md`, `docs/frontend.md`, etc.). Never create or scatter standalone READMEs or markdown documentation in other subdirectories (`client/`, `server/`, etc.).
  - **Root `README.md` Is Maintained Documentation**: The root `README.md` is an active, first-class piece of repository documentation and entry point. Agents must keep its setup instructions, architectural summaries, and verification commands strictly accurate and up-to-date.
  - **Continuous Synchronization**: Whenever a new feature, route, model, script, or configuration is added or changed in the codebase, agents must respectively update all relevant documentation in `docs/` AND the root `README.md` in the same pass.

---

## 2. Strict Type Safety & Code Quality

- **Comprehensive Typing Required**:
  - **TypeScript (`client/`)**: All functions, component props, parameters, return types, variables, API payloads, and DTOs **must be strictly typed**. Avoid `any`; use concrete types from `@/lib/types` or well-defined generics.
  - **Python (`server/`)**: Always write explicit Python type hints for all public functions, class methods, parameters, and return types (e.g., `def sync_technical_admin_credentials(user: User, new_password: str) -> dict[str, Any]:`).
  - Serializer fields and API views must declare explicit validation types, serializers, and OpenAPI schemas via `drf-spectacular` (`@extend_schema`).
- **Zero Typecheck Errors**:
  - Always verify that `npm run typecheck` passes with zero errors before concluding any task.

---

## 3. Core Architectural Axioms & Security

- **Authentication & Token Isolation**:
  - JWT tokens are stored exclusively in secure, HTTP-only, SameSite cookies managed by the Next.js API proxy. The client JavaScript must never store tokens in `localStorage` or `sessionStorage`.
- **Ownership Verification**:
  - Never trust client-supplied owner IDs, product prices, discount amounts, or inventory levels. Derive user and store ownership solely from `request.user` on the server.
- **Role Hierarchy & Credential Isolation**:
  - **Technical Super Admin (`is_superuser=True`)**: System infrastructure owner. Changing this password automatically synchronizes with **MinIO** and **Grafana** via `server/core/auth_sync.py`.
  - **Business Admin (`is_business_admin=True`)**: Platform business operator (manages staff, verifies stores, reviews payouts). **Explicitly isolated** from infrastructure credential sync.
  - **Staff (`is_staff=True`)**: Backoffice operator. Audits orders, processes returns, and manages company official stores.
  - **Customer / Merchant**: Everyday shopper or independent vendor managing their own store.
- **Financial & Escrow Guardrails**:
  - **7-Day Review Escrow**: Sales balances remain in `in_review` for 7 days (the customer refund window) before unlocking to `cleared_net` for merchant payout withdrawals.
  - **Split-Tender Payments**: Shoppers can combine their ProAce Wallet store balance with Stripe card charges. Order cancellations atomically restock physical inventory and immediately refund store credit to the customer's wallet (`SOURCE_REFUND`).
- **CSV Processing**:
  - Bulk catalog imports must use RFC 4180-compliant parsing (`parseCsvRows`) supporting multiline values, quotes, and commas. Naive string `.split(',')` is disallowed.

---

## 4. Mandatory Verification Suite & Testing Hierarchy

Before concluding any implementation or refactoring task, agents must verify changes against the appropriate test tiers:

### Tier 1: Mandatory Offline / Code-Level Verification (Every Task)
These suites require no running servers and **must always be executed and verified with 0 failures**:

```bash
# Frontend Type Checking & Unit Tests
npm run typecheck
npm run test:unit

# Backend Pytest Suite (Full suite: 184 tests)
.venv/bin/pytest server/
```

### Tier 2: Integration & End-to-End Suites (When Dev Servers Are Running)
When both the backend (`python server/manage.py runserver 127.0.0.1:8000`) and frontend (`npm run dev`) servers are running with seeded demo data (`manage.py seed_demo`):

```bash
# 1. API & Proxy Integration Tests (Playwright API tests)
npm run test:integration

# 2. Full Browser End-to-End Tests (Playwright Chromium desktop & mobile)
npm run test:e2e
```

**E2E Test Inventory in `client/tests/`**:
- `api.integration.spec.ts`: Same-origin Next.js proxy token forwarding, authentication cookies, and error payloads.
- `commerce.spec.ts`: Customer browsing, product options, cart additions, and checkout flows.
- `merchant-store.spec.ts`: Merchant onboarding, store profile, product creation, variants, and CSV catalog imports.
- `backoffice.spec.ts`: Staff and administrator backoffice dashboards, order review, and store moderation.
- `self-purchase.spec.ts`: Guardrails preventing merchants from purchasing their own listings.
- `variant-images.spec.ts`: Dynamic variant option selection and image gallery synchronization.
- `ui-stability.spec.ts` & `theme.spec.ts`: Responsive layouts, modal focus trapping, and UI themes.
