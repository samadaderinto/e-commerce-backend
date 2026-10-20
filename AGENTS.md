# ProAce Commerce — Global AI Agent Guidelines & Architecture Rules

This file is the single, canonical source of instructions and operational rules for all AI coding agents working across the repository.

---

## 1. Monorepo Architecture & Single Source of Truth

- **Monorepo Layout**:
  - `client/`: Next.js 15 App Router with React 19 and React Query. The browser UI **must only** communicate via the same-origin `/api/*` proxy route. Direct browser requests to the Django backend origin are strictly forbidden.
  - `server/`: Django REST Framework modular monolith. This is the **authoritative** single source of truth for all business rules, prices, stock limits, user ownership, and access controls.
  - `docs/`: **Canonical Documentation Directory**.
  - `qa-reports/`: **QA & Performance Reports Directory**. Bug audit reports must be saved directly to `qa-reports/bug-audit/`, and performance testing reports must be saved directly to `qa-reports/performance-testing/` (subdivided into `load/`, `stress/`, and `volume/`). Both the `qa-reports/` root directory and all generated report files must strictly remain untracked by git (`.gitignore`).
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
- **Proper Error Handling & Sensitive Information Protection**:
  - **Comprehensive Exception Handling**: All API views, background tasks, external service adapters (Stripe, shipping carriers, notification delivery), and frontend proxy routes must implement explicit, disciplined error handling. Never silently swallow exceptions (`except: pass`) or crash with unhandled 500 server errors.
  - **Zero Exposure of Sensitive Data**: End-user error messages must **never** disclose sensitive system internals, database schema/column names, raw SQL queries, stack traces, filesystem paths, service credentials, API keys, token fragments, or technical Python representations (such as `ErrorDetail(...)`, raw exception reprs, or unparsed dictionary strings).
  - **Structured Backend Logging vs. User-Facing Messages**: Always log internal diagnostic details, exception traces, and provider error codes securely on the server (`logger.error` / `logger.warning`) for observability. Return clean, human-readable, user-friendly messages in the API response envelope (e.g., `{"detail": "Unable to process payment. Please verify your card details or try another payment method."}`).
  - **Frontend Sanitization & Unwrapping**: The client UI must safely unwrap API error envelopes (`error.message`, `error.details`), strip technical prefixes (such as `non_field_errors:`, `detail:`, `code:`, `error:`), and present clear, capitalized, actionable error guidance to the user without exposing code syntax.
- **Zero Typecheck Errors**:
  - Always verify that `npm run typecheck` passes with zero errors before concluding any task.
- **Clean Formatting & Readability**:
  - Code must always be cleanly formatted, properly indented, well-spaced, and readable. Never produce dense, jumbled, single-line blocks (e.g., multi-expression inline JSX tags, squashed handler callbacks, long ternary chains, or unspaced top-level function definitions).
  - Break JSX elements, component props, handler bodies, object literals, and function parameters across clean, structured lines.
  - Maintain consistent 2-space indentation for TypeScript/TSX (`client/`) and PEP 8 4-space indentation for Python (`server/`).
  - Use empty lines to separate distinct logical blocks, top-level functions, classes, and component exports.
- **Dual-Theme Design & Contrast Guardrails (Light & Dark Modes)**:
  - All UI components, layouts, forms, status indicators, badges, progress trackers, and dialogs **must strictly consider and support both Light and Dark themes** (`data-theme='light'` and `data-theme='dark'`).
  - Never design or verify styles exclusively for one mode. Always verify that text, icons, borders, progress bars, active states, and background layers maintain strong WCAG AA/AAA visual contrast across both themes.
  - Avoid hardcoding fixed light/dark hex colors that fail to invert or adapt in dark mode. Use semantic CSS variables (`var(--paper)`, `var(--ink)`, `var(--soft)`, `var(--line)`, `var(--green)`, `var(--muted)`, `var(--button-text)`) or explicit `:root[data-theme='dark']` overrides.
  - When styling multi-state indicators (e.g. active/done/pending steps), ensure active and completed states have distinctive backgrounds and high-contrast foreground icons/text in both themes. Dark mode overrides must never inadvertently flatten active/done elements into the same murky tone as the background.
- **Universal Search & Multi-Criteria Filtering on Main Information Listings**:
  - Whenever a view or main page displays a collection or listing of information (e.g. store orders, product catalogs, customer transactions, payouts, moderation reviews, coupons, audit logs), it **must provide robust search and multi-criteria filtering capabilities**.
  - **Never provide isolated, single-dimension filters alone**: Single-dimension controls (for example, a store orders listing that only filters by order status) are strictly unacceptable for main listing views.
  - **Full Search Capabilities**: Provide debounced text search across key identifying fields (e.g. order IDs, customer names, emails, tracking numbers, product titles, SKUs).
  - **Multi-Dimensional Filters**: Complement text search with orthogonal filters relevant to the domain (e.g. status, date ranges, fulfillment/payment state, price or balance thresholds, categories).
  - **Filter State Management & Reset**: Clearly indicate when filters or search queries are active, and provide a single-click control to reset or clear all active criteria. Empty states must clearly distinguish between a genuinely empty collection and "no results matching current search/filters", guiding the user to clear filters.
  - **Frontend & Backend Synchronization**: Ensure backend list endpoints support corresponding query parameters (`search`, `status`, `start_date`, `end_date`, etc.) with efficient database indexes and queryset filtering, ensuring pagination and count totals stay accurate when filters are applied.

---

## 3. Core Architectural Axioms & Security

- **Authentication & Token Isolation**:
  - JWT tokens are stored exclusively in secure, HTTP-only, SameSite cookies managed by the Next.js API proxy. The client JavaScript must never store tokens in `localStorage` or `sessionStorage`.
- **Ownership Verification**:
  - Never trust client-supplied owner IDs, product prices, discount amounts, or inventory levels. Derive user and store ownership solely from `request.user` on the server.
- **Dynamic, Accurate & Recipient-Scoped Emails**:
  - This rule applies to every email template and dispatch path for shoppers, buyers, merchants, store owners, affiliates, staff, business administrators, technical administrators, and any future profile or role.
  - Build email payloads from authoritative backend records and the actual recipient. Use immutable order, address, tax, and payment snapshots for transaction receipts rather than substituting current profile details or client-supplied values. Resolve ownership and staff/admin access on the server before selecting recipients or including business data.
  - Never invent or hardcode personal or transaction information. Sample names, addresses, ZIP codes, phone numbers, product photos, tracking numbers, carriers, verification codes, bank details, amounts, and statuses must never appear as production fallbacks. Demo data belongs in explicit development seeds and test fixtures only.
  - If an optional value is missing, null, empty, or whitespace-only, omit its entire labeled row, section, image, or link. Do not render empty labels, broken links, fake values, or misleading `N/A`/default statuses. Preserve legitimate zero amounts and quantities; zero is not missing data. Without a real recipient name, use a neutral greeting such as `Hello,`.
  - Match content to the actual event, order composition, and recipient role. Digital-only purchases must omit delivery-address sections and physical-shipment promises even if the customer has a saved address. Physical and mixed orders may show only the recorded delivery details. Show carrier, tracking, bank, refund, payout, and verification details only when they exist and apply to that event.
  - Send customers their own account/order information, merchants their own store information, and operators only information authorized by their role and store assignments. Never disclose another tenant's customer, store, financial, or administrative details. Keep ordinary status emails free of passwords, tokens, and service secrets; dedicated authentication/credential flows must use actual server-generated credentials or links and their existing recipient-verification rules.
  - Keep templates and their backend payload producers synchronized. Validate every changed template and each affected dispatch path, including missing/partial data, unnamed recipients, digital-only orders with and without saved addresses, physical/mixed orders, role/ownership isolation, real zero values, and escaped user-controlled content. Do not treat a template-only change or a successful render with fully populated fixtures as sufficient verification.
  - Persist email/push delivery outbox rows transactionally with their notifications or related business changes; dispatch only after commit. Preserve retry/recovery behavior, prevent duplicate generic and HTML emails for the same event, and do not resend notices for unchanged moderation/access actions. Never claim live inbox delivery was verified solely from rendering or outbox tests.
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
  - **Technical Super Admin Password Immutability**:
    - `populate_fake_data` must **never** reset, overwrite, or interfere with the password of the Technical Super Admin (`admin@proace.local` / `is_superuser=True`).
    - If the Technical Super Admin already exists in the database, seeding must preserve its existing password and credentials entirely intact without interference. Initial fallback credentials apply exclusively when provisioning the technical admin account for the first time on a fresh database.
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
    8. **Seller Verification & Tiers**: 7-tier progression (Starter $0–$4,999, Booster $5,000+, Accelerator $25,000+, Power $100,000+, Mega $500,000+, Legendary $1,000,000+, and Official Partner 0% commission) with mandatory staff compliance onboarding audits.
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

# Backend Pytest Suite (Full suite: 330 tests; 322 passed, 8 offline environment skips)
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

### Tier 3: Pre-Deployment Performance, Security & Bug Audits (Local Execution)
Before shipping features or releases to production, operators run individual performance and security suites locally, and AI agents record bug audits into dedicated report directories. All generated reports must be written exclusively to `qa-reports/` and must remain strictly untracked by git (`.gitignore`):

- **Latest-Only Performance & Security Reports**: Retain only the latest completed run in each performance category (`qa-reports/performance-testing/load/`, `stress/`, and `volume/`) and in `qa-reports/security/`. Keep that run's summary and supporting artifacts together; do not accumulate dated reports, logs, or artifact directories from older runs. Publish the new completed report before removing superseded output so an interrupted run cannot erase the latest available results. A completed run reporting failures is still the latest report and must not be replaced by an older passing result. Cleanup must stay within the corresponding report category and must never delete source code, test fixtures, or unrelated reports. This policy does not change bug-audit report retention.

- **AI Agent Bug Audits**: Whenever an AI agent conducts a bug audit (e.g. reviewing regressions, triage, security inspection, or error-handling audits), the agent must write its comprehensive markdown audit report directly into `qa-reports/bug-audit/` (e.g., `qa-reports/bug-audit/bug-audit-YYYY-MM-DD.md`).
- **Pre-Deployment Performance & Security Testing Commands**:
  ```bash
  # 1. Load Testing (Sustained concurrent browsing, search, and detail requests)
  npm run test:load       # Writes report to qa-reports/performance-testing/load/

  # 2. Stress & Spike Testing (Step-ramp concurrency, instant traffic spikes, inventory race-condition locks)
  npm run test:stress     # Writes report to qa-reports/performance-testing/stress/

  # 3. Volume Testing (Deep pagination LIMIT/OFFSET, multi-criteria filtering, payload serialization)
  npm run test:volume     # Writes report to qa-reports/performance-testing/volume/

  # 4. Security & Data Leak Check (Sensitive data leak detection, role boundary isolation, audit regression suites)
  npm run test:security   # Writes report to qa-reports/security/

  # 5. Full Pre-Deployment QA Suite (Runs all 4 suites sequentially)
  npm run test:qa
  ```


## 5. Automatic Targeted Docker Rebuilds

- **Finish changes with a running update**: After implementation changes and required verification pass, automatically rebuild and recreate the affected local Docker Compose services before concluding. The user's authorization is standing; do not ask them to rebuild manually or request routine confirmation.
- **Rebuild only affected services**: For frontend changes, run `docker compose -f client/compose.yaml up -d --build --no-deps client`. For backend changes, run `docker compose -f server/compose.yaml up -d --build --no-deps api`. Include `notification-worker` and/or `celery-beat` in the backend command when changed code, dependencies, or configuration affects those processes. Changes spanning both applications require both targeted commands.
- **Choose scope from actual dependencies**: Inspect the Compose configuration and changed files. Shared backend modules or backend dependency/image changes may affect API, worker, and scheduler together; rebuild and recreate all affected consumers. Apply required migrations through the updated API container when model changes require them.
- **Preserve infrastructure and data**: Do not rebuild unrelated services, run `down`, delete volumes, reseed databases, or use `--no-cache` merely to refresh application changes. Documentation-only changes do not require image rebuilds.
- **Verify the result**: Check affected container status and health after startup, and inspect logs if startup or health checks fail. Report which services were updated and any remaining failure. A successful image build alone does not establish that the application is running.
- **Handle unavailable Docker honestly**: If Docker is unavailable or a build/startup fails, attempt safe recovery within the authorized scope and report the exact blocker. Never claim the rebuild succeeded or silently leave the user to discover that the running application is stale.
