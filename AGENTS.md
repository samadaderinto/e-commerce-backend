# ProAce Commerce — Global AI Agent Guidelines & Architecture Rules

This file is the single, canonical source of instructions and operational rules for all AI coding agents working across the repository.

---

## 1. Monorepo Architecture & Single Source of Truth

- **Monorepo Layout**:
  - `client/`: Next.js 15 App Router with React 19 and React Query. The browser UI **must only** communicate via the same-origin `/api/*` proxy route. Direct browser requests to the Django backend origin are strictly forbidden.
  - `server/`: Django REST Framework modular monolith. This is the **authoritative** single source of truth for all business rules, prices, stock limits, user ownership, and access controls.
  - `docs/`: **Canonical Documentation Directory**.
    - **Documentation Rule**: Agents **must only** write or update documentation within the `docs/` directory. Do not scatter markdown manuals or project documentation in other subdirectories unless explicitly requested.
    - Whenever code behavior, routes, models, or configurations change, the matching document in `docs/` must be updated in the same pass.

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

## 4. Mandatory Verification Suite Before Finishing Tasks

Before concluding any implementation or refactoring task, agents **must run and verify** all relevant test suites:

```bash
# 1. Frontend Type Safety & Unit Tests
npm run typecheck
npm run test:unit

# 2. Backend Test Suite
.venv/bin/pytest server/
```
All suites must complete cleanly with 0 failures and 0 type errors.
