# Frontend documentation

`client/tests/filter-stability.spec.ts` exercises delayed filter responses for guests, shoppers, buyers, sellers, merchants, staff, business administrators, and technical administrators on desktop and mobile. It verifies retained results, typing focus, mounted controls, same-document shop history, and customer profile stability.

Notification search, tabs, and category filters retain results within the same account and store. Backoffice filter caches and private product previews include the viewer identity; login cancels outstanding queries and clears the prior query cache before activating the new account. External payment and onboarding redirects remain full navigations.

Shop filters update browser history without route navigation. Filtered catalog, merchant, and backoffice queries retain current results while fetching and show a local update status; store and account detail queries discard previous results when the selected entity changes.

Catalog responses expose the backend `visibility` flag. The product page shows the draft preview banner only for explicit `visibility: false`; missing metadata is not evidence of a draft. Hidden products return 404, and unverified-store previews require the store owner or an authorized operator, even with `?preview=1`.

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
  7-day escrow financial breakdown, 4% platform fee calculation, payout requests, inventory health, order fulfillment modal,
  and searchable, multi-filtered merchant orders view with store switcher, search bar, status, timeframe, carrier, and sorting controls.
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
| `NEXT_PUBLIC_GOOGLE_CLIENT_ID` | Public Google OAuth client ID used by Google Identity Services |
| `NEXT_PUBLIC_APPLE_CLIENT_ID` | Public Apple Services ID used by Sign in with Apple JS |

## Social Authentication (Google & Apple)

Customers can sign in or register with one click using Google or Apple:
- **UI Components**: Rendered on `/login` and `/register` above an `or with email` divider.
- **Provider SDKs**: Google Identity Services and Sign in with Apple JS are loaded on demand from the browser. The frontend sends only provider identity tokens through the same-origin `/api/auth/google` or `/api/auth/apple` proxy.
- **Dual-Theme Contrast**: Buttons support Light and Dark themes (`data-theme='light'` / `data-theme='dark'`) via semantic CSS variables (`var(--paper)`, `var(--ink)`, `var(--line)`, `var(--soft)`). The Google icon uses official 4-color SVG paths; the Apple icon uses `fill: currentColor` ensuring maximum WCAG AA/AAA visual contrast.
- **Security Guardrail**: Administrative and staff members are blocked with an explicit error alert if they attempt social sign-in.
- **Affiliate Referral Preservation**: Referral codes (`?ref=CODE`) are captured on arrival, preserved in `sessionStorage` across auth page transitions, and forwarded to the backend on social signup, immediately rewarding the referring marketer.
- **Proxy Token Management**: Next.js proxy intercepts `auth/google`, `auth/apple`, and `auth/social` responses, securely persisting JWT tokens in SameSite HTTP-only cookies (`proace_access`, `proace_refresh`) without exposing tokens to client-side scripts.

## Product Sharing & Link Copying

Shoppers, merchants, and operators can share and copy links to product listings:
- **Share Controls**: Rendered in `purchase-actions` next to the Wishlist Save button, in the product header rating line, and within the `storefront-preview-banner`.
- **Cross-Platform API**: Uses the native Web Share API (`navigator.share`) on supporting mobile/desktop browsers with automatic clipboard copy fallback (`navigator.clipboard.writeText`).
- **Visual Feedback**: Buttons toggle to a green checkmark icon with a "Link copied" / "Copied!" state for 2.5 seconds and trigger a toast notification (`notify('Product link copied to clipboard!')`).
- **Preview Mode Synchronization**: Fully synchronized across live public product pages (`/products/:id`), private operator preview mode (`?preview=1`), and merchant product draft preview (`/merchant/products/preview`), ensuring link sharing works identically in all viewing contexts.

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
- **Merchant Product Editor**: The editor provides a Listing Type selector (`standard` vs `affiliate_clickbank`). Choosing affiliate displays a configuration panel for HopLink URL, vendor nickname, and custom CTA button text, while locking platform discounts to 0%, omitting flash sale timers, and displaying partner pricing notices to prevent fictitious pricing discrepancies. Physical shipping dimensions and variant tables are also bypassed.
- **Backoffice Catalog Audit**: Staff users can filter listings by "ClickBank affiliate offer", view partner offer badges, and inspect outbound HopLinks directly from the store audit table. Coupon creation is strictly disallowed for ClickBank products because checkout is completed externally.

## October commerce audit fixes

Checkout shipping/tax previews include the applied coupon in their query and cache key. Account refund actions require remaining settled funds; cancellation requires every store shipment to remain unfulfilled. Order DTOs expose paid/refunded totals, allocated line amounts, and store fulfillments. Backoffice customer orders (`/admin/orders`) provide multi-dimensional filtering across order lifecycle status, payment tender, and delivery courier (USPS, UPS, FedEx, DHL Express, and Digital) with instant reset and carrier search integration. Generated affiliate URLs enter the same-origin `/api/affiliates/r/` proxy.

Store settings use plain customer-facing labels for store branding, the logo URL, cover image URL, and store announcement. Design references are kept out of the settings interface.

## User Profile Photo & Avatar Management

- **Universal User Avatar Support**: User avatars are rendered across all customer, merchant, and administrative views: header account dropdown trigger, account menu, personal details page (`/account?section=profile`), merchant workspace sidebar footer, and staff/admin audit tables.
- **Interactive Avatar Cropper (`UserAvatarUpload` & `UserAvatarCropDialog`)**: Provides client-side circular crop preview with zoom, pan, and real-time canvas rendering to guarantee standard 512x512 JPEG export conforming to server constraints, managed centrally under Personal Details (`/account/profile`).
- **App Settings & Email Communication Preferences**: The global `/settings` interface provides application appearance toggles (Light / Dark / System). For authenticated users, it dynamically renders an **Email communication preferences** section allowing users to toggle optional emails for **Product recommendations** and **Marketing & promotions** via `PATCH /api/v1/me/`, while preserving mandatory transactional receipts and shipping alerts.
- **Backoffice Profile Isolation**: When administrative users (staff, superadmins, business admins) access `/account` or `/account/profile`, consumer-specific widgets (orders, wallets, addresses, and saved items) and queries are completely excluded. Backoffice users are presented with their personal details (name, email, phone, password management, avatar studio) and quick links to backoffice tools, while shopper-only routes (`/account/orders`, `/account/wallet`, `/account/addresses`) redirect them safely.

ClickBank offer prices are retained only as internal catalog references. Public product cards, detail pages, and listing previews direct shoppers to check the current price on the partner site. Selecting the ClickBank listing type hides ProAce discount and flash-deal controls; the server rejects those promotions and clears them when converting a standard listing.

Store profile pages (`/shop?store=<id>`) list only that store’s products. Filter resets retain the store and any `preview=1` mode; previews remain read-only.

The catalog supports 29 departments shared by homepage category tiles, shop/store filters, and merchant product forms: Electronics, Fashion, Phones, Computing, Sports & outdoors, Books, Toys & games, Kids & baby, Home & living, Kitchen & dining, Beauty & personal care, Health & wellness, Pet supplies, Gaming, Tablets, Fishing, Lingerie & sleepwear, Coffee, tea & drinks, Garden & tools, Automotive, Jewelry & watches, Software & apps, Courses & learning, Templates & planners, Design assets, Photos & video, Music & audio, Business resources, Digital tools & presets. New department keys are validated by Django product choices; apply product migrations before using them. Existing product category keys are preserved.

Backoffice user profiles use a compact identity card with contact and activity details, three financial summary cards, and bordered wallet, activity, and order panels. The layout stacks on smaller screens and respects the active theme.

Dates across customer, merchant, and backoffice records use the shared `DateStamp` component: an unambiguous date (e.g. `10 Oct 2026`) and local 24-hour time without seconds. Table timestamps have separate columns, including Created, Updated, Last active, Requested, Processed, Valid from, and Valid to where applicable. Date fields are never stacked together or joined with slashes in a table cell. Tables scroll horizontally on narrow screens; profile activity uses aligned label/value rows. API timestamps and calendar-input timezone handling remain unchanged.

## Dual-Theme Support & Order Fulfillment Tracker

- **Dual-Theme Accessibility Guardrails**: All storefront, merchant, and backoffice UI components adhere to high-contrast WCAG AA/AAA standards across both light (`data-theme='light'`) and dark (`data-theme='dark'`) themes. CSS semantic variables (`var(--paper)`, `var(--ink)`, `var(--soft)`, `var(--line)`, `var(--green)`, `var(--muted)`, `var(--button-text)`) adapt cleanly without low-contrast flattening.
- **Order Progress Tracker**: The order detail page (`/orders/[id]`) features a 3-stage milestone tracker (Confirmed, Shipped, Delivered) with dynamic state tracking (`done`, `current`, `line-done`):
  - Completed milestones feature filled high-contrast green badges (`#24563f` in light mode with `#fff` checkmark; `#94cfab` in dark mode with `#122219` deep-forest checkmark for 9.8:1 contrast).
  - The connecting track between completed milestones illuminates dynamically in theme green.
  - Pending steps display subtle, distinctive step dots without premature checkmark indicators.
  - Active milestones feature a luminous focus ring indicating the current fulfillment milestone.

Backoffice user-profile order history supports debounced reference/coupon/carrier/tracking search, status (including pickup), courier, payment method, sorting, reset, and 15-row server pagination. Profile order totals and lifetime spend remain independent of order filters.

Backoffice coupon attribution displays the recorded creator’s email. Coupon creation assigns the authenticated staff/admin server-side; records without a creator show “Not recorded” rather than an assumed staff identity.

Partner product details and merchant previews show “Price available on partner site” as a compact supporting note, with pricing determined by the external vendor.


Listing filtering remediation (2026-10-10): payout approvals, merchant payouts and earnings, customer orders/wallet, treasury withdrawals, user/staff management and profile wallet histories now filter before server pagination with matching counts. Finance criteria combine reference search, status/type/method, inclusive UTC date ranges and amount bounds; balances and lifetime totals remain independent of listing filters. Catalog controls expose category, physical/digital and standard/partner types, stock and visibility as applicable. Coupons support type, validity and creator email; stores support official/merchant and creation dates. Saved products filter the complete saved collection before pagination. Notifications support independent read/archive state and category. Search is debounced by 300 ms, criteria changes return to the first page, and reset controls clear active criteria. Invalid financial bounds and pagination return HTTP 400; existing user/store access scopes remain authoritative.

Account activity on shopper, staff, admin, and user-detail profiles uses a shared responsive set of compact cards. Each label stays with its local date and time instead of spreading across the page; semantic surfaces and text colors support both themes. Table timestamps retain their separate aligned columns.


The [notification audit of 11 October 2026](notification-audit-2026-10-11.md) traces order `uuEl5iwv6QMVG`, records reproduced store-filter visibility and duplicate merchant notices, and defines the proposed recipient/channel matrix and remaining delivery/remediation work. Audit findings are not implemented fixes; local console email and disabled FCM do not verify external delivery.


Notification remediation (11 October 2026): one canonical event identity per recipient, recipient-scoped multi-store associations, canonical categories and archived/list filters, selected-store refund reviewer routing, treasury/affiliate/review coverage, transactional inbox/outbox writes, credential outbox delivery, stable email/push queue keys and provider idempotency, shared SSE/FCM toast deduplication, and numeric order-detail links. Apply notification migrations before using the updated API and restart API, notification-worker and celery-beat together. Migration backfills do not send messages; duplicate legacy order-created notices are archived rather than deleted. Local test mode intentionally retains console email and disabled FCM; external provider delivery has not been verified. See the notification audit for channel policy and regression coverage.

Customer order tracking reflects backend Pending, Confirmed, Shipped, Delivered, Picked up, Cancelled, and Refunded states. Terminal states replace the fulfillment tracker with a status notice; digital orders omit shipping. Customer order lists and detail views refresh every 15 seconds while active to reflect staff changes. Cancellation and return actions retain the existing backend rules.

Customer payment labels derive Paid, Awaiting payment, Partial payment, and refund outcomes from authoritative `paid_total`, `refunded_total`, and `total` amounts, rather than labelling every order as paid.

The referral workspace at `/account/affiliates` supports enrollment, copyable `/register?ref=…` invite links, credited-signup progress, and searchable/filterable paginated referral history. Registration accepts the invite code visibly in an optional field. The server grants $25 non-withdrawable ProAce Wallet credit for up to four referred signups; additional referrals remain pending without credit. The displayed earned total is cumulative promotional credit, not a cash balance or ClickBank commission. `/admin/affiliates` lets backoffice operators search/filter enrolled affiliates and review referral totals, credit earned, and account status, with links to existing user management. Customer history omits referred users’ personal information. API endpoints: `/api/v1/affiliates/workspace/` (owner-scoped) and `/api/v1/admin/affiliates/` (backoffice-only).

Digital product onboarding & variant enhancements:
- **Auto-Cover & Smart Photography Card**: When onboarding digital image assets (artwork, wallpapers, photography), the uploaded file immediately populates the storefront cover preview. The Product photography section shows an auto-generated cover card with a `PROACE PREVIEW` badge indicating that no separate cover photo is needed, while preserving an optional upload button for custom promotional banners.
- **Storefront Carousel & Watermark Integration**: On the public storefront and in live merchant preview, digital image previews display the `PROACE PREVIEW` watermark overlay across all gallery and variant images.
- **Digital Options & Variants**: Digital products support edition/resolution variants (e.g. 4K Wallpaper, Mobile HD, Print-Ready Vector). The variant editor displays an "Unlimited digital inventory" badge instead of physical stock counters, permits price adjustments, and syncs variant selection with image switching in the gallery carousel.


Product-page interaction hooks, including share-link feedback state, are initialized before loading/error returns. This keeps hook order stable when asynchronous catalog data arrives and prevents the product page from crashing during guest browsing and checkout.
