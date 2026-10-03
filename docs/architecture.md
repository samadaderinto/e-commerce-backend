# Architecture and API map

This repository is a modular monolith with two separately deployable
applications: a Next.js storefront and a Django REST API. Django owns business
rules and persisted data; the browser UI talks to it through a same-origin
Next.js proxy.

## Repository map

| Path | Responsibility |
| --- | --- |
| `client/src/app/` | Next.js App Router shell, catch-all application page and API proxy route |
| `client/src/components/` | Storefront, cart, account, merchant and reusable UI |
| `client/src/lib/` | Browser API helper, error normalization and shared frontend types |
| `client/tests/` | Unit, proxy integration and browser end-to-end tests |
| `server/storefront/` | Integrated API URL configuration, commerce views/serializers and demo-data command |
| `server/core/` | Shared customer/user, address, review and wishlist domain |
| `server/product/` | Catalog product model, validation policies and search |
| `server/store/` | Merchant stores, store products, moderation and store endpoints |
| `server/cart/` | Shopping cart model and operations |
| `server/payment/` | Orders, checkout, coupons and payment-adjacent workflows |
| `server/notification/` | Notification inbox and asynchronous email/push delivery |
| `server/affiliates/`, `server/staff/` | Referral and staff/admin API functionality |
| `server/observability/` | Health, request instrumentation, metrics, logs and trace setup |
| `server/codematics/` | Django settings package and WSGI/ASGI entry points |
| `server/compose.yaml` | Local API, PostgreSQL, Redis and Elasticsearch services |
| `server/monitoring/` | Local Prometheus, Grafana, Loki, Alloy and Tempo stack |
| `docs/` | Canonical cross-project guides |

## Request and authentication flow

```text
Browser UI
  -> client/src/lib/api.ts
  -> same-origin Next.js /api/* proxy
  -> Django /api/v1/*
  -> Django app views, serializers, policies and models
  -> PostgreSQL (production/Compose) or SQLite (direct local development)
```

The proxy's upstream is configured with `API_URL`, which should include the
`/api/v1` suffix. It attaches access tokens held in HTTP-only cookies, handles
refresh, clears credentials on sign-out and checks same-origin requests for
mutations. Browser components should use the shared `api<T>()` helper rather
than sending requests directly to a backend host. External API clients can call
Django directly with a JWT bearer access token.

The active Django command-line entry point selects
`codematics.storefront_settings`, which uses `storefront.urls`. The older
`codematics.settings` and `codematics.urls` remain in the repository as a legacy
configuration; the duplicate legacy core API routes have been removed. Core
still owns shared user, address, review and wishlist models, plus serializers
that are used by product and staff apps. They are not the integrated storefront
runtime.
When debugging route or setting behavior, start at
[`server/manage.py`](../server/manage.py),
[`server/codematics/storefront_settings.py`](../server/codematics/storefront_settings.py)
and [`server/storefront/urls.py`](../server/storefront/urls.py).

## API route groups

The authoritative route declarations are in
[`server/storefront/urls.py`](../server/storefront/urls.py). The schema is
generated from those views and serializers; use it for method, request/response
and permission details rather than inferring them from a prefix.

| Prefix | Purpose |
| --- | --- |
| `/api/v1/auth/<action>/` | Login, registration, email verification, password reset, token refresh and logout |
| `/api/v1/me/` | Current authenticated account |
| `/api/v1/products/` | Public catalog with Elasticsearch full-text fuzzy search and product details |
| `/api/v1/products/<id>/reviews/` | Product reviews |
| `/api/v1/wishlist/` | Customer saved products |
| `/api/v1/addresses/` | Customer delivery addresses |
| `/api/v1/cart/` | Cart read, item addition, quantity updates and item removal |
| `/api/v1/checkout/` | Checkout with COD, ProAce Wallet balance, or Stripe Wallet |
| `/api/v1/checkout/wallet-session/`, `/wallet-confirm/` | Stripe wallet checkout session and confirmation endpoints |
| `/api/v1/wallet/` | ProAce customer wallet balance and credit/debit transaction log |
| `/api/v1/orders/` | Customer order list, order details, and 7-day refund request endpoints |
| `/api/v1/orders/<id>/tracking/` | Live USPS shipment tracking milestones and status updates |
| `/api/v1/stores/` | Merchant store, product, inventory, schedule, and payout routers |
| `/api/v1/stores/<id>/orders/<order_id>/tracking/` | Merchant fulfillment tracking updates and shipment carrier management |
| `/api/v1/stores/<id>/payouts/` | Merchant payout withdrawal requests against cleared escrow balance |
| `/api/v1/notifications/` | Authenticated notification inbox and device registration |
| `/api/v1/admin/coupons/` | Staff coupon management |
| `/api/v1/admin/stores/` | Store moderation, approval and blocking |
| `/api/v1/admin/staff/dashboard/` | Platform-wide business intelligence, revenue, orders, and store analytics |
| `/api/v1/admin/staff/refunds/` | Customer refund review and moderation queue (7-day window) |
| `/api/v1/admin/staff/payouts/` | Merchant payout request approval and processing |
| `/api/v1/admin/staff/staffs/` | Staff account provisioning, permission toggles, and blocking (Superuser only) |

OpenAPI schema, Swagger and ReDoc are served at `/api/schema/`, `/api/docs/`
and `/api/redoc/` respectively. They are available on a running local backend.
For the exact nested merchant and notification routes, check the included app
routers and generated schema.

## Current design decisions and boundaries

These describe the implementation today, not a promise that every integration
is ready for production:

| Decision | Consequence |
| --- | --- |
| Keep the product in one Django service, divided into domain apps. | Checkout, stock validation, ownership and order snapshots are handled together; new domain behavior should live in its owning app rather than duplicate rules in the UI. |
| Use a same-origin Next.js proxy for browser API traffic. | JWTs stay in HTTP-only cookies and frontend components share one API/error-handling helper. Do not bypass the proxy for browser calls or put tokens in local storage. |
| Keep integrated and legacy Django configurations separate. | `storefront_settings` and `storefront.urls` are the current entry points; the legacy core API surface is removed while shared core domain models remain in use. |
| Derive ownership from authenticated users and validate purchases on the server. | Do not trust client-supplied customer, seller, store or order ownership fields. |
| Restrict product reviews to verified purchasers with up to 3 attached photos. | Only buyers with confirmed completed orders for an item can submit/edit a review, preventing review spoofing and ensuring authentic social proof. |
| Dynamic 6-tier seller milestone hierarchy and official store verification tick. | Store ranks (Starter, Booster, Accelerator, Power, Mega, Legendary) are calculated automatically based on gross volume milestones. |
| JSON-backed product variants with dedicated price modifiers and inventory. | Allows merchants to define options (Size, Color, Material) with independent stock tracking and pricing without relational database overhead. |
| Make Elasticsearch optional and retain a database search fallback. | Local development can run without search, while indexing failures do not become the only path to catalog results. |
| Separate application database from logging infrastructure. | Application emits structured JSON to stdout; Grafana Alloy ships logs to Loki for aggregation in Grafana. |
| Implement 7-day buyer refund review escrow and 4% platform commission. | Merchant earnings from orders placed within the 7-day refund window are held in review before unlocking for withdrawal requests. |
| Use SQLite for direct local development/tests and PostgreSQL for Compose/production. | Direct setup is lightweight; production data must use persistent managed storage. |

## Deployment boundary

The client and server can be hosted separately. Configure the frontend's
`API_URL` to the deployed backend `/api/v1` endpoint and configure the backend's
`FRONTEND_URL` to the exact deployed frontend origin. The current CI/CD deploy
job targets HostGator and is gated on pushes to `main` or `master` after the test,
security, CodeQL and frontend build jobs pass.

Treat [`server/deployment.md`](../server/deployment.md) as the detailed
deployment procedure and secret inventory. The
[infrastructure guide](infrastructure.md) describes local containers and
production service boundaries. Never commit production secrets or env files.
