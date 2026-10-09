# Frontend documentation

Shared frontend styling in `client/src/app/design-system.css` standardizes form controls, buttons, cards, dialogs, catalog typography, and ClickBank partner badges across light and dark themes. Mobile controls use readable input sizes, touch devices expose quick product actions, and reduced-motion preferences are respected.

User management and account details display last login, last activity, and profile revision times. Store governance/public store pages display recorded activity/catalog revisions. Merchant listings show creation/revision dates and support sorting by recent revisions. Backoffice order details expose status/cancellation/refund timestamps; edited reviews display their revision date. Missing historical metadata is shown as “Not recorded”. All metadata comes from the server and is read-only.

Admin and staff record details share a responsive dialog with a labeled header, status badge, two-column definition list (one column on mobile), and print/close actions. Printing isolates the selected record.

The frontend lives in `client/` and is a Next.js App Router application using
TypeScript, React 19, React Query and shared UI components.

## Code map

- `client/src/app/layout.tsx`: app shell root, global metadata and providers.
- `client/src/app/[[...slug]]/page.tsx`: catch-all page router for storefront,
  account, merchant, admin, and help views.
- `client/src/app/api/*`: same-origin API proxy routes that talk to Django.
- `client/src/components/shell.tsx`: shared navigation, search bar, and layout shell.
- `client/src/components/storefront.tsx`: catalog, product detail with selectable variant chips,
  technical specifications and dimensions table, photo review gallery with lightbox, verified buyer review submission,
  review moderation/deletion, flash deal countdowns, store profiles with marquee announcements,
  and quick "Message Store" customer action.
- `client/src/components/cart.tsx`: cart sheet with live coupon code validation, real-time discount line-item display,
  split-tender payments (combining ProAce Wallet with Stripe), multi-carrier rating (USPS, UPS, FedEx, DHL Express with APO/FPO/DPO military guardrails),
  and destination sales tax calculation.
- `client/src/components/account.tsx`: auth, profile, addresses, ProAce Wallet ledger,
  `WalletTopupModal` with quick preset chips (+$25 to +$500), in-app `PasswordChangeModal`,
  order details with live parcel tracking across all carriers, self-service 12-hour order cancellation with atomic restocking,
  and 7-day customer refund submission form.
- `client/src/components/help.tsx`: `HelpPage` (authoritative marketplace FAQs, multi-carrier delivery, 7-day return policy,
  12-hour cancellation, ClickBank affiliate disclosures, seller tiers, and escrow) and `PolicyPage` (`terms` and `privacy`).
- `client/src/components/merchant.tsx`: seller onboarding, dashboard with milestone celebration banners,
  product editor with variant option configuration, RFC 4180-compliant bulk CSV catalog importer (handling quoted fields and multiline data),
  7-day escrow financial breakdown, 4% platform fee calculation, payout requests, inventory health, and order fulfillment modal.
- `client/src/components/admin.tsx`: `AdminDashboardPage` (platform-wide business insights,
  order fulfillment distribution bar chart, store leaderboards), `AdminPayoutsPage` (merchant withdrawal review, approval,
  and rejection with audit notes), `AdminUsersPage` (customer and staff directory with role/status filters and activation toggles),
  and `AdminStaffPage` (staff account creation, permission controls, and blocking).
- `client/src/components/ui.tsx`: reusable controls, product cards, `VerifiedBadge` (seller rank tier icons),
  `FlashCountdown` (real-time sale expiration timer), loading spinners, and small primitives.
- `client/src/lib/api.ts`: browser API helper, error normalization, money
  formatting and category constants.
- `client/src/lib/geo.ts`: ISO 3166-1 alpha-2 country catalog, US states/territories dictionary, dynamic postal code validators, and address normalization.
- `client/src/lib/types.ts`: shared frontend DTO and domain types (`SellerTier`, `ProductVariant`, `Product`, etc.).
- `client/tests/`: unit, integration and Playwright end-to-end tests.

## API access

Browser code calls `/api/*` on the Next.js app, not the Django server directly.
The Next.js proxy forwards requests to the backend API and keeps access/refresh
tokens in HTTP-only SameSite cookies. Client components should use `api<T>()`
from `client/src/lib/api.ts` for normal JSON or `FormData` requests.

The proxy is responsible for:

- forwarding authenticated requests to the Django API;
- refreshing expired access tokens;
- clearing auth cookies during sign-out;
- retrying public catalog, product-detail, and public-store GET requests anonymously after rejected authentication, clearing invalid cookies while preserving sessions during temporary refresh outages;
- hiding raw token values from browser-visible JSON responses;
- enforcing same-origin behavior for browser mutations;
- transparently handling HTTP 3xx redirects via `redirect: 'manual'` and `NextResponse.redirect`, enabling secure outbound partner tracking for ClickBank HopLinks.

Frontend configuration:

| Variable | Purpose |
| --- | --- |
| `API_URL` | Backend API base URL used by the Next.js proxy |
| `E2E_BASE_URL` | Base URL for Playwright e2e tests |
| `E2E_DEMO_PASSWORD` | Password used by e2e tests for seeded demo accounts |
| `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH` | Optional browser executable override |
| `NEXT_PUBLIC_FIREBASE_*` | Public Firebase Web app config and VAPID key for optional browser push |

## Notifications

The notification center uses the authenticated `/api/v1/notifications/` inbox
for in-app notifications. Optional FCM browser alerts supplement that inbox:
configure the `NEXT_PUBLIC_FIREBASE_*` values from the Firebase Web app, enable
messaging and a Web Push certificate in Firebase, then enable FCM on the backend.
The browser opt-in control registers/removes the device through the authenticated
`/api/v1/notifications/devices/` endpoint. The service worker checks the current
session before showing a push notification, so a shared browser does not display
an alert addressed to a different account.

Frontend tools:

- `next`: App Router framework and dev/build/start server.
- `react` and `react-dom`: UI runtime.
- `@tanstack/react-query`: async server-state management.
- `lucide-react`: icon library used by UI controls.
- `typescript`: type checking.
- `node --test`: unit test runner for lightweight frontend tests.
- `@playwright/test`: integration and end-to-end browser testing.

Root npm commands are wired through the workspace in `package.json`; package-level
scripts live in `client/package.json`.

## Separate hosting

The frontend is hostable separately from the backend. In production, set `API_URL`
on the frontend host to the deployed backend URL ending in `/api/v1`.

Production example:

```env
API_URL=http://api:8000/api/v1
```

Local frontend container example:

```env
API_URL=http://host.docker.internal:8000/api/v1
```

The backend must set `FRONTEND_URL` to the deployed frontend origin. That keeps
email links and browser flows aligned after the apps are split across hosts.

The frontend also has its own container setup:

- `client/Dockerfile`: standalone multi-stage Next.js production image (`node:22-alpine`).
- `client/compose.yaml`: modular frontend container runner.
- `compose.yaml` (root): unified full-stack compose running frontend and backend together.
- `client/.dockerignore`: keeps local artifacts, caches, and env files out of the image.

### Building & Running the Frontend Container

To build and run the frontend container individually:
```sh
docker compose -f client/compose.yaml up --build -d
```

To build and run the full stack (Frontend + Backend API + Datastores):
```sh
docker compose up --build -d
```

## UI conventions

- Keep user workflows directly usable from the first screen; avoid replacing app
  views with marketing-only pages.
- Use shared controls from `client/src/components/ui.tsx` before creating new
  one-off controls.
- Keep loading, empty and error states close to the feature that owns them.
- Keep forms explicit about validation and server errors.
- Use `money()` for USD formatting so catalog, cart and order totals stay
  consistent.

## Local commands

From the repository root:

```sh
npm ci
npm run dev
npm run build                  # or npm --prefix client run build
npm run typecheck              # or npm --prefix client run typecheck
npm run test:unit
npm run test:integration
npm run test:e2e
npm run docker:build           # builds all compose services
npm run docker:up              # starts all compose services in background
npm run docker:down            # stops all compose services
```

From `client/`:

```sh
npm run dev
npm run build
npm run start
```

The development app runs at `http://127.0.0.1:3000`. The frontend defaults to
the Django API at `http://127.0.0.1:8000/api/v1`; override `API_URL` in
`client/.env` when needed. `client/.env.example` is the tracked template.

Integration and e2e tests expect the backend and frontend to be running and the
demo accounts to exist.

## Documentation maintenance

Update this file when changing frontend routing, app structure, major components,
browser API behavior, auth-cookie behavior, UI conventions or frontend tests.

## Back-office and carrier checkout

See [role matrix, staff activation, and operator setup](access-control.md) and
[multi-carrier API, environment variables, sandbox setup, and fulfillment boundaries](shipping-integrations.md).

## Product editor preview

Preview opens `/merchant/products/preview` in a separate tab using tab-scoped draft storage. It mirrors the buyer product-detail layout with product gallery, prices, options, seller card, and digital-download label while disabling checkout, save, and seller navigation. The original editor keeps unsaved inputs and uploads. Allow pop-ups for this action; a blocked pop-up produces a visible editor error.

Product saves remember the returned product ID before uploading assets. If an upload fails, Save changes retries against that listing with PATCH. Successful uploads are cleared from the pending queue, and submissions are guarded while a save is running.

Order-status override confirmation requires a nonempty audit reason before enabling Update status. Browser tests cover this requirement and the current wallet checkout flow.

The unsaved product preview displays variant options with selectable prices and images, plus the configured flash deal countdown in the product price block. Expired draft deals show an explanation instead of disappearing.

Admin user profiles use a dedicated responsive two-column layout for the wallet ledger and activity timeline; the panels stack on narrow screens so profile sections do not overlap.

The API proxy expires authentication cookies on authenticated 401 responses only. Anonymous 401 responses do not clear a session created by a concurrent login.

Backoffice navigation uses a dedicated responsive icon navigation row with active-page highlighting, separate from account controls. Overview destinations appear once in the same horizontally scrollable navigation row, including merchant payouts, users, administrator commission withdrawals, and technical-admin Grafana metrics. Required admin and staff password changes use a focused security card with password confirmation and a visibility toggle.

Store onboarding requires a complete business address (street, city, state/region, country and postal code). Products may be saved as drafts, but manual and scheduled publication require that address for both digital and physical listings.

Time handling: Django stores timezone-aware UTC instants (`TIME_ZONE=UTC`, `USE_TZ=True`). Browser date/time inputs display local time and submit ISO UTC timestamps. Dashboard requests accept a validated IANA `time_zone` (UTC by default); the browser supplies its timezone for local calendar-day reporting. Date-only chart labels are preserved without timezone shifts. Cron and carrier request clocks use aware UTC; flash countdowns include minutes.

Military postal delivery: APO/FPO/DPO destinations use USPS only with the currently supported integrations. Checkout disables other carrier options and the server rejects unsupported carriers in both demo and live rating and payment flows. Address city/state/ZIP must agree: AA uses 340xx, AE uses 090xx–098xx, AP uses 962xx–966xx, with country United States. This is a supported-service policy, not a claim that all commercial postal handoff services are prohibited: UPS Ground Saver and Mail Innovations have military-address support but are not integrated here. See [USPS military addressing standards](https://pe.usps.com/text/dmm300/703.htm) and [UPS supported services](https://www.ups.com/us/en/support/shipping-support/print-shipping-labels/how-to-write-address). ZIP blocks alone do not guarantee an active destination or eligibility for every USPS service; live carrier availability and military mail content/customs requirements still apply.

Cart mutations submit a `variant` option name alongside product and quantity, and rendered cart products expose `selected_variant`. Distinct options have separate cart rows. CSV imports limit files to 2 MB / 500 rows, reject ambiguous numeric price formats and show failed row numbers. The same-origin proxy deduplicates refresh calls, preserves sessions during upstream outages and sets access-cookie lifetime from the upstream JWT expiry. See [audit remediation](security-audit-remediation.md) for verification and operational boundaries.

## ClickBank Partner Storefront & Editor Experience

- **Catalog & Cards**: Products configured as `affiliate_clickbank` render distinctive orange "Partner Offer" and "ClickBank" badges on product cards. The "Add to bag" action is replaced by a direct outbound tracking anchor (`/api/affiliates/clickbank/outbound/${product.id}`) opening in a secure new tab (`target="_blank"`, `rel="noopener noreferrer"`).
- **Product Detail**: Detail pages replace local quantity selectors and stock countdowns with an "Official Partner Listing · In Stock" notice and a partner delivery card indicating fulfillment by ClickBank and the partner vendor.
- **Merchant Product Editor**: The editor provides a Listing Type selector (`standard` vs `affiliate_clickbank`). Choosing affiliate displays a configuration panel for HopLink URL, vendor nickname, and custom CTA button text, while hiding physical shipping dimensions and variant tables.
- **Backoffice Catalog Audit**: Staff users can filter listings by "ClickBank affiliate offer", view partner offer badges, and inspect outbound HopLinks directly from the store audit table.

## October commerce audit fixes

Checkout shipping/tax previews include the applied coupon in their query and cache key. Account refund actions require remaining settled funds; cancellation requires every store shipment to remain unfulfilled. Order DTOs expose paid/refunded totals, allocated line amounts, and store fulfillments. Generated affiliate URLs enter the same-origin `/api/affiliates/r/` proxy.

Store settings use plain customer-facing labels for store branding, the logo URL, cover image URL, and store announcement. Design references are kept out of the settings interface.

## User Profile Photo & Avatar Management

- **Universal User Avatar Support**: User avatars are rendered across all customer, merchant, and administrative views: header account dropdown trigger, account menu, personal details page (`/account?section=profile`), application settings (`/settings`), merchant workspace sidebar footer, and staff/admin audit tables.
- **Interactive Avatar Cropper (`UserAvatarUpload` & `UserAvatarCropDialog`)**: Provides client-side circular crop preview with zoom, pan, and real-time canvas rendering to guarantee standard 512x512 JPEG export conforming to server constraints.
- **App Settings & Account Profile Routes**: Users and backoffice operators can manage their profile pictures from both the global `/settings` interface and the `/account` profile tab.
- **Backoffice Profile Isolation**: When administrative users (staff, superadmins, business admins) access `/account` or `/account/profile`, consumer-specific widgets (orders, wallets, addresses, and saved items) and queries are completely excluded. Backoffice users are presented with their personal details (name, email, phone, password management, avatar studio) and quick links to backoffice tools, while shopper-only routes (`/account/orders`, `/account/wallet`, `/account/addresses`) redirect them safely.
