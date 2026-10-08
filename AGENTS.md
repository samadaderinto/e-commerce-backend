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
  - **All READMEs Except Root in `docs/`**: All documentation and README files—**with the sole exception of the root `README.md`**—must reside exclusively within `docs/` (e.g., `docs/README.md`, `docs/architecture.md`, `docs/frontend.md`, `docs/backend.md`, etc.). Never create or scatter standalone READMEs or markdown documentation in other subdirectories (`client/`, `server/`, etc.).
  - **Root `README.md` Is Maintained Documentation**: The root `README.md` is an active, first-class piece of repository documentation and entry point. Agents must keep its setup instructions, architectural summaries, and verification commands strictly accurate and up-to-date.
  - **Continuous Synchronization**: Whenever a new feature, route, model, script, or configuration is added or changed in the codebase, agents must respectively update all relevant documentation in `docs/` AND the root `README.md` in the same pass.

---

## 2. Strict Type Safety & Code Quality

- **Comprehensive Typing Required**:
  - **TypeScript (`client/`)**: All functions, component props, parameters, return types, variables, API payloads, and DTOs **must be strictly typed**. Avoid `any`; use concrete types from `@/lib/types` or well-defined generics.
  - **Python (`server/`)**: Always write explicit Python type hints for all public functions, class methods, parameters, and return types (e.g., `def sync_technical_admin_credentials(user: User, new_password: str) -> dict[str, Any]:`).
  - Serializer fields and API views must declare explicit validation types, serializers, and OpenAPI schemas via `drf-spectacular` (`@extend_schema`).
- **Serialization Safety**:
  - Never pass raw non-primitive objects (such as `PhoneNumber` instances from `PhoneNumberField`, `Decimal`, `UUID`, or custom models) inside ad-hoc dictionaries returned via `Response(...)`. Always coerce them explicitly (e.g. `str(phone or '')`) or route through an explicit DRF `Serializer` to prevent `TypeError: Object of type X is not JSON serializable` crashes during JSON rendering.
- **Zero Typecheck Errors**:
  - Always verify that `npm run typecheck` passes with zero errors before concluding any task.
- **Clean Formatting & Readability**:
  - Code must always be cleanly formatted, properly indented, well-spaced, and readable. Never produce dense, jumbled, single-line blocks (e.g., multi-expression inline JSX tags, squashed handler callbacks, long ternary chains, or unspaced top-level function definitions).
  - Break JSX elements, component props, handler bodies, object literals, and function parameters across clean, structured lines.
  - Maintain consistent 2-space indentation for TypeScript/TSX (`client/`) and PEP 8 4-space indentation for Python (`server/`).
  - Use empty lines to separate distinct logical blocks, top-level functions, classes, and component exports.

---

## 3. Core Architectural Axioms & Security

- **Authentication & Token Isolation**:
  - JWT tokens are stored exclusively in secure, HTTP-only, SameSite cookies managed by the Next.js API proxy. The client JavaScript must never store tokens in `localStorage` or `sessionStorage`.
- **Ownership Verification**:
  - Never trust client-supplied owner IDs, product prices, discount amounts, or inventory levels. Derive user and store ownership solely from `request.user` on the server.
- **Canonical Seeding & The Administrative Triad**:
  - `populate_fake_data` is the **authoritative, single command** for local and development database seeding. The legacy `seed_demo` and `seed_fake_data` alias commands are removed.
  - Seeding must **always** provision and guarantee the complete administrative triad:
    1. **Technical Super Admin**: `admin@proace.local` (`is_superuser=True`, `is_staff=True`, `is_business_admin=False`). Infrastructure owner and root system administrator.
    2. **Business Admin**: `business-admin@proace.local` (`is_business_admin=True`, `is_staff=True`, `is_superuser=False`). Platform operations, staff management, payout review, store verification.
    3. **Staff Backoffice**: `staff@proace.local` (`is_staff=True`, `is_superuser=False`, `is_business_admin=False`). Operational audits, order reviews, and official company store maintenance.
  - It also provisions key commerce profiles:
    - `seller@proace.local` (single active store: Apex Athletics)
    - `merchant@proace.local` (flagship multi-store vendor: ProAce Select & Aura Audio, tier coverage)
    - `shopper@proace.local` and `buyer@proace.local` (customer buyers with active carts/orders)
  - **Credential Fallback Order**:
    1. CLI option `--password <secret>` if explicitly provided.
    2. `DEFAULT_ADMIN_PASSWORD` / `TECHNICAL_ADMIN_PASSWORD` from `.env` if configured.
    3. Standard fallback dev password: `ProaceDemo2026!`.
- **Infrastructure Credential Synchronization**:
  - Django application media storage uses dedicated service credentials (`MINIO_ACCESS_KEY=commerce-media` and `MINIO_SECRET_KEY`). Application code never depends on MinIO root credentials for file storage or retrieval.
  - Technical Super Admin password updates trigger external service synchronization via `server/core/auth_sync.py`:
    - **Grafana**: Synchronized via Grafana's HTTP REST Admin API (`PUT /api/admin/users/1/password`).
    - **MinIO**: Synchronized via the MinIO Client (`mc`) CLI to update the technical admin user's credentials and guarantee the `consoleAdmin` policy for direct web dashboard access at `:9001`. If `mc` is unavailable or MinIO is offline, the operation degrades gracefully without blocking the user's Django password update.
- **DRY Environment Variable Substitution**:
  - Never repeat values for shared credentials, passwords, usernames, or service DSNs across `.env` and `.env.example` files.
  - Always declare the primary source once (e.g. `DEFAULT_ADMIN_EMAIL`, `DEFAULT_ADMIN_PASSWORD`, `POSTGRES_USER`, `POSTGRES_PASSWORD`) and use bash-compatible variable substitution for all dependent variables (e.g. `TECHNICAL_ADMIN_EMAIL=${DEFAULT_ADMIN_EMAIL}`, `TECHNICAL_ADMIN_PASSWORD=${DEFAULT_ADMIN_PASSWORD}`, `GRAFANA_ADMIN_PASSWORD=${DEFAULT_ADMIN_PASSWORD}`, `MINIO_ROOT_PASSWORD=${DEFAULT_ADMIN_PASSWORD}`, `POSTGRES_EXPORTER_PASSWORD=${POSTGRES_PASSWORD}`).
- **Financial & Escrow Guardrails**:
  - **7-Day Review Escrow**: Sales balances remain in `in_review` for 7 days (the customer refund window) before unlocking to `cleared_net` for merchant payout withdrawals.
  - **Split-Tender Payments**: Shoppers can combine their ProAce Wallet store balance with Stripe card charges. Order cancellations atomically restock physical inventory and immediately refund store credit to the customer's wallet (`SOURCE_REFUND`).
- **Multi-Jurisdiction Destination Sales Taxes**:
  - Destination taxes are computed via a hybrid engine (`payment.TaxJurisdiction` local rules with pluggable Stripe Tax fallback).
  - Tax rates support 5 decimal places of precision (`max_digits=7, decimal_places=5`) for municipal ZIP-code overrides.
  - Every order must persist an immutable `Order.tax_snapshot` regulatory audit payload.
  - Backoffice operators manage tax jurisdictions and ZIP overrides via `/admin/taxes` and `/api/v1/admin/taxes/`.
- **CSV Processing**:
  - Bulk catalog imports must use RFC 4180-compliant parsing (`parseCsvRows`) supporting multiline values, quotes, and commas. Naive string `.split(',')` is disallowed.
- **Platform Policies, Terms & FAQ Consistency**:
  - All consumer-facing and merchant-facing policies, FAQs, legal terms, and help articles across `client/src/components/help.tsx`, `client/src/lib/business.ts`, `docs/`, and the root `README.md` must remain strictly unified, accurate, and aligned with backend operational reality:
    1. **7-Day Return & Escrow Window**: Physical items have a 7-day post-delivery customer refund window; sales balances remain in `in_review` for 7 days before unlocking to `cleared_net` for merchant payout requests.
    2. **12-Hour Cancellation Window**: Orders not yet marked as shipped by the merchant can be cancelled within 12 hours with atomic inventory restocking and immediate ProAce Wallet store credit refund (`SOURCE_REFUND`).
    3. **Multi-Carrier Shipping & Military Guardrails**: Physical delivery supports USPS, UPS, FedEx, and DHL Express with dynamic rate quoting based on parcel weight and dimensions. Military APO/FPO/DPO destinations are supported exclusively via USPS. Digital goods have $0 shipping worldwide.
    4. **Payment Methods & Split-Tender**: Native checkout supports major credit/debit cards (Visa, Mastercard, Amex, Discover), Apple Pay, and Google Pay via Stripe, ProAce Wallet store credit, and split-tender payment.
    5. **Destination Sales Taxes**: Destination taxes are computed automatically with 5-decimal precision and persisted in `Order.tax_snapshot`.
    6. **Commission & Fee Structure**: Standard merchant stores pay a 4% platform processing fee (sellers keep 96%); Official Partner stores retain 100% of sales with 0% commission.
    7. **ClickBank & Affiliate Partnerships**: Curated partner listings display "Official Partner Listing" badges and route to external vendor checkouts via encrypted HopLinks with 0% cart contamination; fulfillment and refunds are managed under ClickBank's 60-day customer satisfaction guarantee with FTC-compliant affiliate disclosures.
    8. **Seller Verification & Tiers**: 6-tier progression (Starter, Booster, Accelerator, Power, Mega, Official) with mandatory staff compliance onboarding audits.
  - Whenever any policy, fee, carrier, return window, or affiliate rule is added or modified in the codebase, agents must synchronize `help.tsx`, `business.ts`, `docs/`, and the root `README.md` in the exact same pass.

---

## 4. Mandatory Verification Suite & Testing Hierarchy

Before concluding any implementation or refactoring task, agents must verify changes against the appropriate test tiers:

### Tier 1: Mandatory Offline / Code-Level Verification (Every Task)
These suites require no running servers and **must always be executed and verified with 0 failures**:

```bash
# Frontend Type Checking & Unit Tests (24 unit tests)
npm run typecheck
npm run test:unit

# Backend Pytest Suite (Full suite: 237 tests)
.venv/bin/pytest server/
```

### Tier 2: Integration & End-to-End Suites (When Dev Servers Are Running)
When both the backend (`python server/manage.py runserver 127.0.0.1:8000`) and frontend (`npm run dev`) servers are running with seeded demo data (`manage.py populate_fake_data`):

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
