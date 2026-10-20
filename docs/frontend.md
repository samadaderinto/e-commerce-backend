# Frontend

The frontend uses Next.js 15 App Router, React 19, TypeScript, and React Query.
It serves the customer storefront, account pages, merchant workspace, and
backoffice from one application.

## Code map

| Path | Responsibility |
| --- | --- |
| `src/app/[[...slug]]/page.tsx` | Server route resolution and redirects |
| `src/components/route-components.tsx` | Dynamic feature-component loading |
| `src/app/api/[...path]/route.ts` | Same-origin backend proxy and auth cookies |
| `src/components/shell.tsx` | Shared navigation, account controls, and layout |
| `src/components/providers.tsx` | Session, theme, query, and application providers |
| `src/components/storefront.tsx` | Home, discovery, catalog, and product pages |
| `src/components/cart.tsx` | Bag and checkout interfaces |
| `src/components/account.tsx` | Profile, addresses, orders, wallet, and customer settings |
| `src/components/merchant.tsx` | Stores, catalog editor, orders, teams, and merchant finances |
| `src/components/admin.tsx` | Backoffice operations and platform finances |
| `src/components/notifications.tsx` | Notification inbox and navigation |
| `src/components/help.tsx` | Help, policies, and terms interfaces |
| `src/components/ui.tsx` | Shared controls, cards, badges, countdowns, and dialogs |
| `src/lib/api.ts` | Typed API helper and error normalization |
| `src/lib/types.ts` | Shared API and domain types |
| `src/lib/business.ts` | Displayed business rules and policy descriptions |
| `src/lib/geo.ts` | Countries, US regions, postal validation, and address normalization |
| `tests/` | Unit, proxy integration, and browser tests |

## Routing and application areas

The catch-all server page resolves a route, performs relevant redirects, and
selects a feature component. Feature bundles load through dynamic imports with
SSR enabled. Shared shell/providers stay available across navigation.

Customers use the home feed, `/shop`, product pages, cart, checkout, and
`/account` workspaces. Merchants use `/merchant` for store/catalog operations,
orders, refunds, finances, and team management. Operators use `/admin` for
customer access, moderation, taxes, refunds, payouts, and reporting.

Navigation reflects active permissions, but hidden links are not an access
control boundary. Django must authorize every private read and mutation.
Use [access control](access-control.md) and the route resolver for exact paths.

## API access and authentication

Browser code uses the typed `api<T>()` helper with same-origin `/api/*` URLs.
The proxy translates these to the server-only `API_URL`, including its
`/api/v1` prefix. Never put the upstream origin in browser fetches or expose
credentials through public environment variables.

The proxy owns access/refresh cookies, refresh coordination, logout, and
same-origin mutation checks. Browser JavaScript does not read JWTs or persist
them in local/session storage. Public catalog reads can recover from stale auth
cookies without turning a delayed response into a logout of a newer session.

Errors pass through shared envelope normalization. Display concise actionable
messages, not raw DRF objects, technical prefixes, provider errors, or stack traces.
Keep request/response types synchronized with backend serializers.

## State and listings

React Query manages server reads, freshness, and invalidation. Session, active
store, and recipient-sensitive data must remain correctly scoped when switching
accounts/stores. Do not share private financial response caches across users.

Main listings combine debounced search with independent filters such as status,
date, type, amount, role, category, and carrier. Backend filtering precedes
pagination; changing criteria returns to the first page. Provide a clear reset
action and distinguish no matching results from a genuinely empty collection.

Guest cart/saved-item browser persistence is optional. Storage failures must leave
the current in-memory session usable; reload persistence cannot be guaranteed
when the browser denies storage.

## Customer commerce

Product pages keep option selection, price, availability, and gallery images in
sync. Future drops and unavailable products cannot be made purchasable by a
client countdown or stale cart state. ClickBank offers link to external vendor
checkout and never enter the native bag.

Checkout collects the applicable address, shipping quote, tax, coupon, and
payment choice. The backend recalculates totals and eligibility. Stripe returns
are confirmed server-side before navigating to the actual order. Do not create
or display a paid order solely because the browser returned from Stripe.

Order details use recorded item and fulfillment data. Digital access is a protected
download, not a public media URL. Refund editing retains the selected order and
the backend's return-window/settlement state. Failed attempts still show the
responsible operator where authorized.

Saved bank/Stripe payout destinations are managed at
`/account/payout-accounts`. Show masked identifiers and submit saved IDs, not
trusted routing/account payloads from a displayed form.

## Merchant and backoffice interfaces

Merchant product editing includes drafts, variants, specifications, media,
preview, schedules, and RFC 4180 CSV imports. Unsaved previews are distinct from
publishing. Team workspaces separate Owner, Admin, Catalog Manager, and
Fulfillment Specialist capabilities.

Order fulfillment and refund views remain scoped to the selected store.
Financial views distinguish review holds, cleared funds, reservations, debt, and
payout state rather than treating gross sales as withdrawable money.

Backoffice listings provide detail links on identifying references and separate
action controls. Destructive/moderation/financial decisions require explicit
confirmation and applicable reasons. Show actual staff/admin action identity
without inferring an operator from the current viewer.

## Notifications and picture search

Inbox navigation resolves event links for the current recipient and active store
membership. Email/push delivery and the inbox record are separate concerns.
Firebase libraries load only when push configuration is available.

Notification SSE uses the same browser origin. When configured,
`NOTIFICATION_STREAM_URL` routes only the stream to a dedicated backend process;
token refresh still uses the primary API. Do not silently redirect failed stream
traffic into the interactive API pool.

Picture search state lives in `visual-search-context.tsx`. Uploads, pending
recognition, offered item choices, results, clearing, and retries form an explicit
lifecycle. Stale requests must not restore cleared/replaced results. Unknown
images should not produce unrelated inventory or invented match percentages.
See [local picture search](visual-search.md) for model limits and setup.

## Styling and accessibility

Use semantic theme variables such as `--paper`, `--ink`, `--line`, `--muted`,
and `--button-text`. Verify light and dark modes, including active/completed
states, status badges, borders, disabled controls, and focus indicators.

Use labeled fields, keyboard-operable controls, focus-managed dialogs, readable
errors, and responsive tables. Preserve an obvious hierarchy between references,
status, and actions. Shared UI belongs in reusable primitives rather than
duplicated per-page styling.

## Development and verification

From the repository root:

```sh
npm run dev
npm run typecheck
npm run test:unit
npm run build
```

With seeded frontend/backend services running:

```sh
npm run test:integration
npm run test:e2e
```

Browser tests cover desktop/mobile workflows and both themes. Unit checks do not
establish real provider delivery or production latency. See
[performance](performance.md) for tracing and representative measurements.

Rebuild only the client after frontend source changes:

```sh
docker compose -f client/compose.yaml up -d --build --no-deps client
```

Configure `API_URL` and `FRONTEND_URL` for separate hosting; browser requests
still use the same-origin proxy. See [deployment](deployment.md) for secrets
and private-service networking.

