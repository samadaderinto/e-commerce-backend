## Design system and styling conventions

Shared frontend styling in `client/src/app/design-system.css` standardizes form controls, buttons, cards, dialogs, catalog typography, and ClickBank partner badges across light and dark themes. Mobile controls use readable input sizes, touch devices expose quick product actions, and reduced-motion preferences are respected.

Admin and staff record details share a responsive dialog with a labeled header, status badge, two-column definition list (one column on mobile), and print/close actions. Printing isolates the selected record.

- **Typography & Brand Identity**: Clean Swiss-inspired typography utilizing system fonts and high-contrast ink (`--ink: #0a140d`, `--paper: #ffffff`, `--soft: #f4f7f5`). Distinctive forest green accents (`--green: #15803d`, `--green-light: rgba(21, 128, 61, 0.08)`).
- **Responsive Conventions**: Fluid `.container` layouts with mobile breakpoint at 650px and tablet/split stacking at 1024px. Interactive elements enforce `min-width: 0` with explicit overflow clamping.
- **Accessible Dialogs & Modals**: Modals utilize backdrop blur, trapped focus, background scroll-lock (`body:has(.dialog-backdrop)`), `Escape` key listeners, and explicit accessible ARIA headings (`role="dialog"`, `aria-modal="true"`).

## Modals & Interactive Primitives

1. **Wallet Top-Up Modal (`WalletTopupModal`)**:
   - Offers quick-select amount chips (`+$25`, `+$50`, `+$100`, `+$250`, `+$500`) alongside custom numeric inputs constrained to `$5 – $5,000`.
   - Directly triggers `/api/v1/wallet/topup-session/` and seamlessly transitions shoppers into payment flows.
2. **In-App Password-Change Modal (`PasswordChangeModal`)**:
   - Renders current password, new password, and confirmation fields with inline show/hide visibility toggles (`Eye` / `EyeOff`).
   - Validates 8-character minimums and matching confirmation locally before posting to `/api/v1/password/change/`.
3. **Cart Coupon & Split-Tender Controls (`CartSheet`)**:
   - Instant coupon code input with real-time `/api/v1/checkout/validate-coupon/` validation.
   - Dynamic discount line-item with one-click removal badge.
   - Split-tender payment toggles allowing buyers to apply ProAce store wallet credits directly against Stripe checkout charges.
4. **Order Cancellation & Refund Interactions (`OrderPage`)**:
   - Eligible orders (`pending`, `confirmed`) expose a destructive "Cancel order" action with confirmation warning.
   - Orders within the 7-day post-delivery window provide item-by-item return selection, reason capture, and refund destination routing (instant wallet store credit vs. original payment method).
5. **Robust RFC 4180 CSV Parsing (`MerchantProducts`)**:
   - Implements a state-machine CSV parser (`parseCsvRows`) supporting multiline records, embedded commas, and escaped quotes (`""`), preventing broken product rows during bulk catalog uploads.
6. **Destination Sales Tax Management (`AdminTaxesPage`)**:
   - Accessible at `/admin/taxes` via the backoffice navigation bar for staff and administrators.
   - Summarizes active calculation mode (`Local Database Engine` vs. `Stripe Tax (Automated)`), total rules, and active municipal ZIP overrides.
   - Instant search by state code, jurisdiction name, or postal code prefix, with active status filters.
   - Interactive modal dialog with focus trapping for adding ZIP overrides, editing statutory rates, and toggling shipping or digital goods taxability.
   - One-click "Restore 50 US Baselines" action with confirmation to initialize statutory state rates.

## Shared pagination

`Pagination` in `client/src/components/ui.tsx` takes `page`, `totalPages`, and `onChange`. It anchors first/last pages, includes the active page and one neighbour on each side, and inserts noninteractive ellipses for gaps. Previous/next buttons have accessible labels and disable at boundaries; the current page uses `aria-current="page"`. Below 650px, page numbers collapse to `Page N of M` between the navigation buttons. Offset lists translate using `(page - 1) * pageSize`.

## Add to bag

`AddToBagButton` shares the product-card and product-detail interaction:

1. Idle: requested selector quantity exceeds the current committed quantity.
2. Loading: synchronous ref lock prevents rapid clicks; CTA disables and shows a spinner.
3. Success: cart cache/local state updates; `Added!` appears for 1.8 seconds, followed by the committed in-bag count.
4. No-op: clicking again with an unchanged target quantity cannot send another mutation. Raising the selector sends only the difference needed to reach that target.
5. Unavailable: stock exhausted, quantity over stock, own listing, unverified seller, cart load/error, or stock cap disables the CTA. At the cap, display `Max quantity in bag`.

The provider also locks concurrent additions by product ID and validates positive integer quantities and combined stock. Guest updates use functional state to avoid stale cart writes. The backend remains the final inventory authority and validates checkout stock atomically. Existing product variants share a product-ID cart line; this change does not introduce separate variant SKU inventory.

## Four-carrier checkout state and dynamic service tiers

Exactly four branded radio options appear: UPS, FedEx, DHL, USPS. Changing carrier purges previous service selections and resets delivery fees to prevent orphaned rates. The query key includes carrier, address, product IDs, and quantities. While rates fetch, clear the active quote and render loading skeleton feedback; the payment CTA remains disabled. Once rates resolve, the lowest-cost/recommended plan is preselected automatically.

Each selectable service tier card renders:
- Official branded service title (e.g. UPS Ground, FedEx Priority Overnight, DHL Express Worldwide, USPS Ground Advantage).
- Normalized classification benefit badge (`Fastest`, `Best Value`, `Standard`, `Economical`).
- Transit window estimate (e.g., "Next business day by 10:30 AM / 12:00 PM", "Est. 2–5 business days").
- Live calculated rate or `Free`.

Selecting or toggling a service plan reactively recalculates the order summary (subtotal + tax + shipping fee) and updates the payment button. The selected quote token is sent to checkout; backend validation and payment metadata use its signed carrier/service snapshot.

Live rate failures display the provider error rather than falling back to demo prices. Demo prices require explicit development configuration. See [Shipping integrations](shipping-integrations.md).

## Live transport and room topology

Authenticated clients connect to `GET /api/v1/notifications/stream/` through the same-origin `/api/notifications/stream` proxy. This is Server-Sent Events (SSE), using Redis Pub/Sub and the existing database notification inbox. Cookies remain HTTP-only; the Next proxy forwards/refreshed JWT authentication and streams the upstream body without JSON buffering.

Room topology is deliberately recipient based: Redis channel `commerce:events:user:{id}`. The server derives the channel from the authenticated user and ignores requested room names. Domain routing expands a store's owner, assigned staff, and administrators into recipient channels; users never subscribe directly to arbitrary `store:{id}` or administrative rooms. Account status and credential version are rechecked during streaming.

Frames:

| SSE name | Payload | Client action |
| --- | --- | --- |
| `ready` | `{ "resync": true }` | Refresh active queries on initial connection and reconnect. |
| `state` | `{ "event": string, "notification_id"?: number, "title"?: string, "data"?: object }` | Refresh active queries; show a deduplicated toast for `notification.created`. |
| `resync` | `{ "reason": "broker_unavailable" }` | Refresh durable state; reconnect. |

Domain event dictionary:

| Event | Data | Audience |
| --- | --- | --- |
| `store_created` | `store_id` | Active staff and both administrator roles. |
| `verification_submitted` | `store_id` | Business and technical administrators. |
| `store.changed` | `store_id` | Owner, assigned staff, administrators; assignment changes also reach removed staff to clear stale state. |
| `order_placed`, `order_paid`, `shipping_updated` | `order_id`, `store_ids`, `status` | Customer confirmations, store owners, assigned staff, administrators. |
| `order.changed` | `order_id` | Customer tracking/payment screens. |
| `inventory_low` | `store_id`, `product_id`, `available` | Assigned staff and administrators; emitted on crossing five units or reaching zero. |
| `inventory.changed` | `store_id`, `product_id` | Store owner, assigned staff, administrators. |
| `notification.created` | Notification ID, title, underlying domain data | That notification's recipient only. |
| `notification.changed` | Notification ID when available | Recipient; includes read/unread/archive/delete and mark-all-read. |

Events publish only after transaction commit; rolled-back mutations cannot dispatch them. Redis Pub/Sub does not replay missed messages: the inbox is persisted in the database and reconnect refreshes authoritative API state. Failed/closed connections retry with exponential backoff up to 30 seconds; while offline, active queries refresh every 30 seconds. Background notification polling remains a recovery path. Email and FCM push use the existing durable delivery outbox; deployment requires verified email/push credentials. SMS delivery is not configured in this project.

Operational configuration: `REALTIME_REDIS_URL` optionally selects a dedicated Redis; otherwise use `CACHE_URL`, then localhost Redis. Run the shipped Gunicorn `gthread` configuration (32 threads per worker by default, override `GUNICORN_THREADS`). Each stream lasts at most 25 seconds and reconnects after 3 seconds, ensuring token renewal and bounded worker occupancy. Reverse proxies must preserve `text/event-stream`, disable buffering/cache, and allow at least 35-second upstream reads. Monitor concurrent streams and size threads/workers accordingly; SSE connections each consume a WSGI thread. ASGI deployment would require an async stream implementation.

## API reference

All notification endpoints are scoped to the signed-in recipient:

- `GET /api/v1/notifications/`: paginated inbox, with `state`, `store`, `limit`, and `offset` filters.
- `GET /api/v1/notifications/counts/`: unread/read/archive totals.
- `POST /api/v1/notifications/{id}/mark-read/` and `/mark-unread/`.
- `POST /api/v1/notifications/mark-all-read/`.
- `POST /api/v1/notifications/{id}/archive/` and `/restore/`.
- `POST /api/v1/notifications/devices/` with `{ "token": "FCM device token" }`; DELETE with token unregisters it. FCM must be enabled.
- `GET /api/v1/checkout/shipping-rates/?address={id}&carrier=UPS` (also FEDEX, DHL, USPS).

For complete checkout payloads and carrier credentials, see [Shipping integrations](shipping-integrations.md). For roles and administrative operations, see [Access control](access-control.md).

## Verification matrix

| Area | Required scenarios |
| --- | --- |
| Layout | Catalog, product, checkout, account selector, merchant inventory/orders, seller verification, staff dialog at 360–430px, 768px, 1024px, desktop; document scrollWidth must not exceed viewport; broad tables scroll internally. |
| Pagination | 1/last boundaries; active window at middle page; large totals stay bounded; mobile compact text; empty/single-page lists hide control. |
| Bag | Rapid clicks, quantity two, unchanged selector, increasing target, stock cap, zero stock, own listing, backend failures; reload preserves committed cart. |
| Shipping | Four radios; each carrier returns its own plans; switch back to cached carrier; stale service cleared; loading disables payment; quote totals and tax; provider failure shows error; mixed/digital baskets. |
| Live events | Commit vs rollback; unassigned staff excluded; unauthenticated stream rejected; malicious requested room ignored; read state updates; reconnect refresh; Redis failure preserves inbox; disabled credentials terminate stream; multiple browser tabs. |
| External delivery | Email/FCM outbox retry, device removal, duplicate delivery handling; no real provider requests in isolated unit tests. |

Automated coverage: `client/tests/ui-stability.spec.ts`, `client/tests/backoffice.spec.ts`, `client/tests/theme.spec.ts`, `server/notification/test_realtime.py`, and existing notification/shipping/storefront tests. Run frontend typecheck and unit tests, mocked Playwright tests, and Django tests with isolated test settings.

Transport references: [Redis Pub/Sub delivery semantics](https://redis.io/docs/latest/develop/use-cases/pub-sub/) and [Django StreamingHttpResponse](https://docs.djangoproject.com/en/6.0/ref/request-response/#streaminghttpresponse-objects).
