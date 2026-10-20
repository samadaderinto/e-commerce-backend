# Backend

The backend is a Django REST Framework modular monolith. It owns authentication,
permissions, catalog eligibility, pricing, tax, stock, payments, and financial
records. Frontend values are inputs to validate, not authoritative business state.

## Entry points and module map

`server/manage.py` selects `codematics.storefront_settings`; the integrated API
routes are declared in `server/storefront/urls.py`. The base settings package
also supports specialized test and notification-stream configurations.

| Module | Responsibility |
| --- | --- |
| `core/` | Users, addresses, shopper wallets, reviews, saved items, and shared filters |
| `product/` | Product models, catalog search, indexing, and local picture search |
| `store/` | Merchant stores, team permissions, catalog management, earnings, and payouts |
| `cart/` | Customer carts and selected product variants |
| `payment/` | Checkout, orders, taxes, refunds, funding, accounting, and fulfillment |
| `notification/` | Recipient inboxes, delivery outbox, email, push, and SSE |
| `affiliates/` | Referral accounting and ClickBank outbound attribution |
| `staff/` | Platform operations and backoffice endpoints |
| `storefront/` | Integrated serializers, views, and API composition |
| `observability/` | Health probes, metrics, structured logs, and tracing |

Important payment modules are `services.py` for checkout/order operations,
`accounting.py` for tender and allocation calculations, `fulfillment.py` for
store-level shipment state, `funding.py` for wallet deposits,
`checkout_recovery.py` for abandoned/compensated checkout, and
`provider_events.py` for provider adjustments.

## API and authentication

The frontend proxy forwards browser calls from `/api/*` to `/api/v1/*`.
Direct API consumers can use supported bearer authentication. Browser tokens
must stay in HTTP-only cookies, not local/session storage.

Views derive the acting user from authentication. Store access is resolved
through ownership and active team membership. Role-sensitive operations require
their actual permission, not merely a client-supplied store or owner ID.
See [access control](access-control.md) for the role matrix.

Serializers validate API inputs and normalize error messages. Financial/date
filters run before pagination so counts and results describe the same scope.
Public errors omit SQL, paths, raw provider exceptions, credentials, and traces.
Internal logs retain diagnostic detail.

OpenAPI endpoints are `/api/schema/`, `/api/docs/`, and `/api/redoc/`.
Use the route declarations and generated schema for exact methods and payloads.

## Catalog and merchant stores

Public eligibility requires a visible, unblocked product in an eligible store.
Scheduled drops use server time. Merchant draft previews require authorized
access; a preview parameter alone never makes drafts public.

Products can have variant-specific stock, price modifiers, SKUs, and images.
An empty cart variant identifies the main product; it is not an arbitrary
fallback for an unknown option. Physical products need shipping measurements;
digital products use protected purchased-file delivery.

Merchant CSV imports use RFC 4180 parsing, including quoted commas, escaped
quotes, and multiline values. Store administrators can manage branding and
settings; catalog and fulfillment roles remain scoped to their work.

Store team invitations support both linked users and pending email recipients.
Membership changes and recipient notices are transactional. Inviting, accepting,
resending, and revoking access remain separate operations. Active memberships
control store navigation, queries, and notification destinations.

### Seller tiers and commissions

| Tier | Gross-sales threshold |
| --- | --- |
| Starter | Below $5,000 |
| Booster | $5,000 |
| Accelerator | $25,000 |
| Power | $100,000 |
| Mega | $500,000 |
| Legendary | $1,000,000 |
| Official Partner | Platform-managed partner classification |

Standard stores pay a 4% platform fee. Official Partner stores pay 0%.
Verification and moderation remain independent of a store's sales tier.
Products under moderation and stores with financial history cannot be removed
in ways that erase their retained records.

## Checkout, orders, and fulfillment

Checkout re-reads eligible products, variants, prices, coupons, tax, and stock
from backend records. Inventory changes and financial mutations use database
transactions and row locks. Native carts cannot contain external ClickBank offers.

Stripe supports cards and supported Apple Pay/Google Pay wallets. ProAce Wallet
can pay alone or alongside a Stripe charge. Checkout attempts durably record
wallet reservations and provider sessions so retries can recover without
duplicating a payment or releasing funds while a session can still complete.

Orders preserve item, address, tax, and tender snapshots. Historic order detail
does not substitute today's product price or customer's current address.
Each store has its own fulfillment membership and shipping history; one merchant
cannot expose or mutate another store's shipment.

Physical delivery uses USPS, UPS, FedEx, and DHL Express rates based on destination
and parcel measurements. Military APO/FPO/DPO destinations require USPS.
Digital goods carry no shipping charge and omit physical delivery promises.
See [shipping integrations](shipping-integrations.md).

### Cancellation, returns, and merchant balances

Unshipped orders can be cancelled within 12 hours. Accepted cancellation restocks
eligible physical inventory atomically and immediately returns customer store
credit through a refund wallet receipt.

Physical return eligibility runs for seven days after delivery. Physical merchant
proceeds remain in review until seven days after recorded store delivery and no
earlier than the sale hold. Undelivered physical proceeds stay held; digital
proceeds use the seven-day sale hold.

Refunds retain cumulative settled amounts, tender allocation, operator identity,
and stock-return state. Partial refunds do not imply that the entire order is
refunded. Refund and cancellation retries cannot issue the same wallet credit
or restock the same accepted return twice.

Payouts draw only from cleared funds, recheck reservation coverage on approval,
and retain debt or dispute holds. Bank destination values are encrypted at rest,
owner-scoped, masked in responses, and resolved server-side from saved IDs.
Preserve the application secret key or migrate encrypted records before rotation.
A treasury destination records transfer intent; it does not itself execute an
external bank/Stripe transfer.

### Wallet integrity and compensation

Wallet credits and debits require positive, finite, exact-cent amounts within
the database range. Credits also check resulting balance capacity while holding
the wallet lock. Idempotency keys identify prior receipts and reject conflicting
amounts, owners, or transaction directions. Legitimate negative recovery balances
are retained rather than silently reset.

Checkout and funding compensation complete only after a provider refund reports
`succeeded`. Pending, action-required, failed, and unknown results stay recovery
work. Pending create responses are retrieved for current settlement state.
Provider idempotency keys and wallet receipt keys persist across retries.
Split wallet reservations are not released prematurely.

## Destination taxes

`payment.TaxJurisdiction` stores destination rules and ZIP overrides with
five-decimal rate precision. The engine supports Stripe Tax fallback and records
the calculation in immutable `Order.tax_snapshot`, including jurisdiction,
taxable merchandise/shipping, exemptions, and provider context.
Operators manage jurisdictions at `/admin/taxes` and `/api/v1/admin/taxes/`.

## Provider adjustment reconciliation

Apply all migrations before starting API, worker, stream, and scheduler consumers.
Subscribe Stripe webhooks to:

- `checkout.session.completed` and `checkout.session.expired`
- `charge.refunded`
- `refund.created`, `refund.updated`, and `refund.failed`
- `charge.dispute.created`, `charge.dispute.updated`, and `charge.dispute.closed`

Signature verification precedes processing. `ProviderAdjustment` stores unique
refund/dispute references and applied amounts. Order locks serialize callbacks;
current provider state resolves out-of-order updates. Failed reconciliation
returns a retryable response rather than acknowledging unapplied changes.

Refund approval requires settlement. External card refunds adjust tender and
merchant earnings without assuming physical goods returned. Merchant reversals
use merchandise allocation, not refunded tax/shipping. Multi-store allocations
use cent-safe largest-remainder distribution. Disputes hold funds until resolved;
lost disputes reverse earnings and won disputes release holds.

Referral rewards require a fully paid qualifying order and are reversed on
cancellation/refund. Already-spent promotional credit can produce wallet debt.
ClickBank products instead use external vendor checkout and its fulfillment and
60-day satisfaction policy; they never enter native payment/refund flows.

## Notifications and email

Business events persist recipient-scoped inbox and outbox rows transactionally.
Dispatch starts after commit. A Celery worker sends email/push; Beat recovers
pending or abandoned attempts. Store associations and destination links require
the recipient's active access.

Delivery attempts use an incrementing attempt number as a lease fence. Only the
current processing attempt may persist success, failure, or remaining push tokens.
This protects database state when an old worker finishes late. It cannot undo
an external request already in flight or guarantee exactly-once provider delivery.

Templates live in `server/templates/email-templates/`. Payload producers use
actual recipients and authoritative transaction snapshots, omit missing optional
rows, preserve zero amounts, escape user content, and distinguish digital from
physical orders. Credential notices use dedicated protected flows, not generic
status emails. Rendering or queuing a message does not establish inbox delivery.

See [getting started](getting-started.md) for console/Resend setup and
[observability](observability.md) for delivery diagnostics.

## Search, cache, and media

Elasticsearch returns candidate IDs/counts; PostgreSQL hydrates current records.
Database fallback keeps catalog reads available when search is disabled or
unusable. Durable indexing jobs support retry/recovery after search outages.
Rebuild indexes using `python server/manage.py rebuild_product_index`.

Public catalog snapshots and shard search caching are performance mechanisms,
not business locks. Authenticated/private responses must not be shared across
users. See [performance](performance.md) for cache scope and worker budgets.
[Picture search](visual-search.md) documents the separate local inference service.

MinIO provides local S3-compatible media storage with dedicated application
credentials, separate from root/console access. Enabled storage requires its
dependencies; it must not silently fall back to ephemeral application files.
Purchased digital assets remain authorization-checked streams.

## Development seeding

The canonical command is `core/management/commands/populate_fake_data.py`.
The storefront command forwards to it; there are no separate seed aliases.

| Preset | Users | Stores | Products | Orders | Reviews |
| --- | --- | --- | --- | --- | --- |
| small | 25 | 6 | 45 | 90 | 70 |
| medium | 65 | 12 | 150 | 350 | 280 |
| large | 200 | 25 | 500 | 1,500 | 1,100 |
| huge | 500 | 50 | 1,200 | 4,000 | 3,200 |

Use `--users`, `--stores`, `--products`, `--orders`, and `--reviews` to
override volumes. Counts describe generation inputs, not an exact final database
size: known accounts/scenarios may be reused and supporting rows are also added.
At least 11 users and positive overrides are required.

The command is development-only, transactional, and refuses `DEBUG=False`.
It preserves an existing technical-admin password; other known demo accounts
can be refreshed. Password precedence is CLI, configured admin password, then
the documented development fallback. Output never prints that password.

`--clear` deletes commerce data throughout the database, not only tagged fake
rows. It is unnecessary for adding volume. Search indexing runs after commit.
See the [root guide](../README.md#development-data) for the 10,000-record command.

## Verification and operation

```sh
.venv/bin/pytest server/
.venv/bin/python server/manage.py makemigrations --check --dry-run
```

Offline settings isolate cache, email, storage, and broker dependencies.
PostgreSQL locking tests use `codematics.concurrency_test_settings`, which creates
and destroys only `test_proace_audit_47_49`. It rejects that name as the application
database. Do not auto-approve deletion of an unexpectedly existing test database:

```sh
docker compose -f server/compose.yaml exec -T api python manage.py test \
  core.test_wallet_integrity_audit notification.test_delivery_lease_audit \
  payment.test_compensation_settlement_audit payment.test_inventory_concurrency \
  payment.test_audit_regressions.PostgresConcurrencyTests \
  --settings=codematics.concurrency_test_settings
```

For backend changes, apply migrations and rebuild the affected consumers as
described in [infrastructure](infrastructure.md). Verify running health, not only
image build success. Technical-admin password updates synchronize Grafana and
MinIO through `core/auth_sync.py`; external-service failure must not block the
Django password update.
