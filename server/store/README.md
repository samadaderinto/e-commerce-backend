# Merchant API

Merchant backend for store onboarding, catalog management and dashboard data.
All routes require `Authorization: Bearer <access-token>`. Store ownership comes
from the authenticated user; supplied `user` and `store` fields cannot transfer
ownership. Other merchants' stores/products return 404.

## Store Setup

`POST /stores/` creates a store. `POST /stores/create/` is also supported.

```json
{
  "name": "Lagos Electronics",
  "username": "lagos-electro",
  "profile": {"email": "shop@example.com", "bio": "Electronics and accessories"},
  "address": {
    "address": "12 Market Road",
    "country": "Nigeria",
    "state": "Lagos",
    "city": "Ikeja",
    "zip": "100001"
  }
}
```

`username`, `profile` and `address` are optional. A username is generated when
omitted. Nested onboarding is atomic: invalid contact/address data creates no store.

| Method | Route | Purpose |
| --- | --- | --- |
| GET | `/stores/` | Paginated list of your stores |
| GET, PATCH | `/stores/{id}/` | Read/edit store name and username |
| GET, PATCH | `/stores/{id}/profile/` | Contact email, bio, social links and phones |
| GET, PUT | `/stores/{id}/pickup-address/` | Read/replace the default pickup address |
| GET | `/stores/{id}/onboarding/` | Contact, address and catalog completion checks |

Completion is a setup checklist, not merchant identity verification or approval.
Store deletion is not exposed because it would cascade into cart/order history.

## Product Onboarding

`POST /stores/{id}/products/`:

```json
{
  "title": "Wireless Headphones",
  "description": "Over-ear Bluetooth headphones",
  "category": "electronics",
  "price": "25000.00",
  "discount": 10,
  "available": 25,
  "tags": ["audio", "wireless"]
}
```

New products default to drafts (`visibility=false`), with zero stock and zero
discount when omitted. Price must be positive, stock nonnegative and discount
between 0 and 60. Category uses the existing Product category choices. Ratings,
sales and sponsorship are read-only. Set `visibility=true` to publish and
`visibility=false` to unpublish. Hard deletion is rejected to preserve history.

| Method | Route below `/stores/{id}/products/` | Purpose |
| --- | --- | --- |
| GET | `` | Paginated catalog |
| GET, PATCH, PUT | `{product}/` | Details and edits |
| PATCH | `{product}/inventory/` | Set stock with `{"available": 25}` |
| GET, POST | `{product}/images/` | List/upload images; multipart field `image` |
| DELETE | `{product}/images/{image}/` | Remove an image belonging to this product |
| GET, PUT | `{product}/specifications/` | Read/replace specifications |

Images must be valid JPEG, PNG or WebP files, at most 5 MB. Specifications require
`serial` (unique), `attributes`, `height`, `width`, `breadth`, `weight`, and `color`.
Dimensions and weight must be positive. Existing model precision permits two
decimal places and a maximum value of 99.99; units remain a client convention.

Catalog query parameters: `search`, `category`, `visibility=true|false`,
`stock=in|low|out`, `ordering`, `limit`, `offset`. Low stock means 1-5 units;
out means zero. Ordering supports `created`, `updated`, `price`, `available`,
`title`, `sales`, prefixed with `-` for descending. Default page size is 20,
maximum 100. Product changes invalidate catalog and affected active-cart caches
after commit. Redis shares cache revisions across workers; LocMem is per process.

## Dashboard And Orders

`GET /stores/{id}/dashboard/?days=30&low_stock_threshold=5` returns:

- All-time inventory totals, published/draft counts and stock alerts.
- Order counts by status within the selected period (1-365 calendar days, UTC).
- Daily order counts, including zero-count days.
- Units sold and top products from orders marked ordered with status confirmed,
  shipped, delivered or picked up.
- Estimated item value using current product prices and discounts.

Estimated value is **not historical revenue or a payout balance**. Checkout does
not yet snapshot item prices or allocate coupons, shipping, taxes and fees per
seller. Pending, cancelled, refunded and unplaced orders are excluded from sales.
Multi-store carts contribute only this merchant's items.

`GET /stores/{id}/orders/?status=confirmed` returns paginated order references,
status, placement flag, creation time and this merchant's product quantities.
It excludes customer identity, other merchants' items and shared cart totals.
Fulfillment status changes and payouts are not exposed: the current order model
has one global status for an entire cart, which may contain multiple sellers.

## Scheduled Publishing

- `POST /stores/schedules/` with `product` and a future ISO-8601 `make_visible_at`.
- `GET /stores/schedules/` lists your schedules.
- `GET`, `DELETE /stores/schedules/{id}/` reads/cancels a schedule.
- Run `python manage.py publish_scheduled_products` periodically through your
  deployment scheduler. Creating a schedule alone does not run a background job.

The command publishes due products once, leaves future schedules intact and
invalidates affected caches. The existing product cron class uses the same service.

## Migrations And Verification

New migrations align store contact columns and the order/cart relationship with
the existing models. The core migration removes the obsolete `is_verified`
column (auth uses `is_active`) and fixes review ordering. The order reference
default now generates a new value per order. Review these migrations before
applying them to a populated deployment, then run `python manage.py migrate`
with the deployment's normal settings and dependencies.

From the repository root:

```sh
.venv/bin/python codematics/manage.py test store --settings=codematics.test_settings
```

This runs real API requests and real migrations against a fresh in-memory SQLite
database. The test profile excludes optional mail, notification, search, profiler
and payment-service integrations; it is not a deployment configuration. Tests
cover access tokens, ownership, atomic onboarding, validation, images, stock,
cache invalidation, dashboard filtering, mixed-store orders and scheduled publishing.

The repository-wide migration drift check still encounters pre-existing changes
outside this feature, including a required `Refund.email` field without a data
migration. Resolve that separately before generating a full migration set.
No frontend merchant dashboard is included; these endpoints supply its data.

The normal application startup check currently stops at the pre-existing
`event_notification.apps.EventNotificationConfig` setting: the local package is
named `notification`. Full-project startup and optional integrations have not
been validated by this isolated merchant test suite.
