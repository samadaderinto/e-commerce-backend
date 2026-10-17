# Frontend documentation

## Optional storage and public-read recovery

Guest cart/saved-item storage writes tolerate `SecurityError` and quota failures;
the active in-memory session remains usable, but reload persistence cannot be
guaranteed when browser storage is unavailable. `ui-stability.spec.ts` exercises
both errors on desktop/mobile while adding an item and navigating to the bag.

For explicitly public GET routes only, a failed refresh transport, timeout, or
malformed refresh response allows an anonymous retry using Django's normal
visibility rules. Temporary failures do not clear refresh cookies. Private reads,
writes, and cancelled requests never gain anonymous recovery. The existing
main-API refresh target and deduplication remain unchanged. Route-level unit
tests in `proxy-refresh.test.mjs` cover these failure and isolation cases.

Route loading uses a client-side `next/dynamic` registry in
`client/src/components/route-components.tsx`, retaining SSR and server-side route
selection while loading only the selected feature group. Firebase SDK imports are
deferred until browser push is configured. See [performance](performance.md) for
bundle measurements, caveats and the browser regression command.

`/account/payout-accounts` is a dedicated My Account page for bank and Stripe payout destinations, with encrypted identifiers, masked account suffixes, modal creation/editing, deletion and default selection. Account overview links to this page rather than embedding account management. Treasury withdrawals show the selected destination in a compact checkout-style summary; changing it opens a modal where operators can select, add, edit, delete, or set a default destination, with a link to the full payout accounts page in the modal. Only the selected destination ID is submitted for server-side resolution. Stripe destinations identify the intended target for an audited transfer request; saving one does not execute a transfer. `/settings/bank-accounts` redirects to the My Account page. Treasury withdrawals group amount and method in a compact responsive row, show available funds in the section header, and keep the selected destination and content-sized submit action together within a 620px form. Successful async submission resets the captured form element safely. Google and Apple controls share a 400px-wide, 44px-high reserved area; Google retains its provider-rendered credential button. Background loading indicators are positioned without adding/removing table height, and the staff directory reserves a status area so active-filter controls do not shift mobile results. Merchant startup waits for the saved store rather than briefly mounting the first store. Staff directory role filters omit privileged roles. Payout approvals separate Bank, Bank account and Routing and use compact row actions. `/orders/stripe-return` confirms the server-side Stripe session and replaces the URL with the resulting order details page.

`client/tests/filter-stability.spec.ts` exercises delayed filter responses for guests, shoppers, buyers, sellers, merchants, staff, business administrators, and technical administrators on desktop and mobile. It verifies retained results, typing focus, mounted controls, same-document shop history, and customer profile stability.

Notification search, tabs, and category filters retain results within the same account and store. Backoffice filter caches and private product previews include the viewer identity; login cancels outstanding queries and clears the prior query cache before activating the new account. External payment and onboarding redirects remain full navigations.

Shop filters update browser history without route navigation. Filtered catalog, merchant, and backoffice queries retain current results while fetching and show a local update status; store and account detail queries discard previous results when the selected entity changes.

Catalog responses expose the backend `visibility` flag. The product page shows the draft preview banner only for explicit `visibility: false`; missing metadata is not evidence of a draft. Hidden products return 404, and unverified-store previews require the store owner or an authorized operator, even with `?preview=1`.

On a product detail page, the rating summary's review count selects the Reviews tab and scrolls the tab panel into view.

Shared frontend styling in `client/src/app/design-system.css` standardizes form controls, buttons, cards, dialogs, catalog typography, and ClickBank partner badges across light and dark themes. Use the shared `.button.compact` variant for dense actions (12px text, 36px minimum height) and `.button.compact.pill` for rounded contact actions instead of inline sizing. Backoffice and merchant heading actions use the same compact metrics at every breakpoint. Mobile controls use readable input sizes, touch devices expose quick product actions, and reduced-motion preferences are respected.

User management and account details display last login, last activity, and profile revision times. Store governance/public store pages display recorded activity/catalog revisions. Merchant listings show creation/revision dates and support sorting by recent revisions. Backoffice order details expose status/cancellation/refund timestamps; edited reviews display their revision date. Missing historical metadata is shown as “Not recorded”. All metadata comes from the server and is read-only.

Admin and staff record details share a responsive dialog with a labeled header, status badge, two-column definition list (one column on mobile), and print/close actions. Printing isolates the selected record.

The frontend lives in `client/` and is a Next.js App Router application using
TypeScript, React 19, React Query and shared UI components.

## Code map

- `client/src/app/layout.tsx`: app shell root, global metadata and providers.
- `client/src/app/[[...slug]]/page.tsx`: catch-all page router for storefront,
  account, merchant, admin, and help views.
- `client/src/app/api/*`: same-origin API proxy routes that talk to Django.
- `client/src/components/shell.tsx`: shared navigation, search bar with integrated AI Visual Lens camera trigger, and layout shell.
- `client/src/components/visual-search-modal.tsx`: `VisualSearchModal` (multimodal AI visual shopping and "Shop The Look" workspace; drag-and-drop/browse/clipboard paste upload, interactive bounding box hotspot overlays on detected items, extracted color palette swatches, curated sample looks test drive, keyword refinement, and ranked visual affinity matches).
- `client/src/components/storefront.tsx`: catalog, product detail with selectable variant chips,
  technical specifications and dimensions table, photo review gallery with lightbox, verified buyer review submission,
  secure HTTPS review-photo URL attachments, author/store-owner/backoffice review removal, flash deal countdowns, store profiles with marquee announcements,
  and quick "Message Store" customer action.
- `client/src/components/cart.tsx`: cart sheet with live coupon code validation, real-time discount line-item display,
  split-tender payments (combining ProAce Wallet with Stripe), reference-scoped Stripe cancellation recovery, multi-carrier rating (USPS, UPS, FedEx, DHL Express with APO/FPO/DPO military guardrails),
  and destination sales tax calculation.
- `client/src/components/account.tsx`: auth, profile, addresses, ProAce Wallet ledger,
  `WalletTopupModal` with quick preset chips (+$25 to +$500), in-app `PasswordChangeModal`,
  order details with live parcel tracking across all carriers, self-service 12-hour order cancellation with atomic restocking,
  and 7-day customer refund submission form.
- `client/src/components/help.tsx`: `HelpPage` (authoritative marketplace FAQs, multi-carrier delivery, 7-day return policy,
  12-hour cancellation, ClickBank affiliate disclosures, seller tiers, and escrow) and `PolicyPage` (`terms` and `privacy`).
- `client/src/components/merchant.tsx`: seller onboarding, dashboard with milestone celebration banners,
  product editor with variant option configuration, scheduled store drop configuration (`drop_at`), RFC 4180-compliant bulk CSV catalog importer (handling quoted fields and multiline data),
  7-day escrow financial breakdown, 4% platform fee calculation, payout requests, inventory health, order fulfillment modal,
  searchable, multi-filtered merchant orders view with store switcher, search bar, status, timeframe, carrier, and sorting controls,
  and **Store Team Access (`MerchantTeam`)** at `/merchant/team` featuring member rosters, role badges (Owner, Admin, Catalog Manager, Fulfillment Specialist), invite modal with email lookup and role scoping descriptions, role modification, member removal confirmations, and role-aware navigation and deep-link route protection (`<Empty title="Access Restricted" ... />`).
  Stripe payout settings refresh Connect status after returning from onboarding, show connected or pending-review states, and allow merchants to resume only when Stripe reports required details still due.
- `client/src/components/admin.tsx`: `AdminDashboardPage` (platform-wide business insights,
  order fulfillment distribution bar chart, store leaderboards), `AdminPayoutsPage` (merchant withdrawal review, approval,
  and rejection with audit notes), and `AdminCommissionPage` (treasury withdrawal requests with note-required external completion/failure actions), `AdminUsersPage` (customer and staff directory with role/status filters and activation toggles),
  and `AdminStaffPage` (staff account creation, permission controls, and blocking; photo/name links open the full staff profile, with a separate quick-details dialog). In the customer and user directory, the avatar/name link opens the profile; row actions are reserved for block/activate controls. Staff directory names and avatars also link to `/admin/users/:id`; staff actions remain separate. In admin listings, store names link to the dedicated store profile; payout references, order IDs, coupon codes, refund IDs, and refund order IDs open their detail dialogs, with redundant Details buttons removed.
- `client/src/components/ui.tsx`: reusable controls, product cards, `VerifiedBadge` (seller rank tier icons),
  `FlashCountdown` (real-time sale expiration timer), `DropCountdown` (live product drop release timer with zero-refresh client unlocking), live drop viewer presence indicators, loading spinners, and small primitives.
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
- expiring root-path auth cookies with the same attributes used at sign-in during sign-out and invalid-session cleanup, including the backend's empty HTTP 204 logout response;
- aborting pending browser API requests when sign-out starts and propagating browser cancellation through the proxy, preventing an in-flight token refresh from restoring the signed-in session;
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

For Docker builds, these `NEXT_PUBLIC_*` values are embedded into the browser
bundle at build time. Rebuild the client after changing either value; changing
only the running container environment does not update the sign-in buttons.

## Social Authentication (Google & Apple)

Customers can sign in or register with one click using Google or Apple:
- **UI Components**: Rendered on `/login` and `/register` above an `or with email` divider.
- **Provider SDKs**: Google Identity Services renders its official sign-in button so users can explicitly choose a Google account even when One Tap is skipped. Sign in with Apple JS is loaded on demand. The frontend sends only provider identity tokens through the same-origin `/api/auth/google` or `/api/auth/apple` proxy.
- **Dual-Theme Contrast**: Buttons support Light and Dark themes (`data-theme='light'` / `data-theme='dark'`) via semantic CSS variables (`var(--paper)`, `var(--ink)`, `var(--line)`, `var(--soft)`). The Google icon uses official 4-color SVG paths; the Apple icon uses `fill: currentColor` ensuring maximum WCAG AA/AAA visual contrast.
- **Security Guardrail**: Administrative and staff members are blocked with an explicit error alert if they attempt social sign-in.
- **Session recovery**: A logout clears the current device's signed-in UI state even when the backend cannot confirm refresh-token revocation; the user is told when that revocation needs attention.
- **Affiliate Referral Preservation**: Referral codes (`?ref=CODE`) are captured on arrival, preserved in `sessionStorage` across auth page transitions, and forwarded to the backend on social signup, immediately rewarding the referring marketer.
- **Proxy Token Management**: Next.js proxy intercepts `auth/google`, `auth/apple`, and `auth/social` responses, securely persisting JWT tokens in SameSite HTTP-only cookies (`proace_access`, `proace_refresh`) without exposing tokens to client-side scripts.

## Product Sharing & Link Copying

Shoppers, merchants, and operators can share and copy links to product listings:
- **Share Controls**: Rendered in `purchase-actions` next to the Wishlist Save button, in the product header rating line, and within the `storefront-preview-banner`.
- **Product Detail Copy Controls**: The product page copy controls write the current product URL to the clipboard on the first click and show confirmation; they do not open the operating system share sheet. If the Clipboard API is unavailable or rejects the write, a selection-based copy fallback is used.
- **Visual Feedback**: Buttons toggle to a green checkmark icon with a "Link copied" / "Copied!" state for 2.5 seconds and trigger a toast notification (`notify('Product link copied to clipboard!')`).
- **Preview Mode Synchronization**: Fully synchronized across live public product pages (`/products/:id`), private operator preview mode (`?preview=1`), and merchant product draft preview (`/merchant/products/preview`), ensuring link sharing works identically in all viewing contexts.

## Notifications

The notification center uses the authenticated `/api/v1/notifications/` inbox
for in-app notifications. Optional FCM browser alerts supplement that inbox:
configure the `NEXT_PUBLIC_FIREBASE_*` values from the Firebase Web app, enable
messaging and a Web Push certificate in Firebase, then enable FCM on the backend.
The browser opt-in control registers/removes the device through the authenticated
`/api/v1/notifications/devices/` endpoint, and queries device registration state directly from the backend database via `GET /api/v1/notifications/devices/?token=<token>` on startup to guarantee UI synchronization across tabs and browsers. The service worker checks the current
session before showing a push notification, so a shared browser does not display
an alert addressed to a different account.

Signed-in users can enable or disable browser alerts in the expandable Browser
alerts section of `/settings`; it reports unsupported browsers and blocked
permissions with recovery guidance. The backoffice notification menu provides
the same device control, stays within the viewport, and synchronizes its state
with the backend database and App Settings when either control changes the device registration.
Registration waits for the root-scope Firebase service worker to activate before
requesting an FCM token. Store suspension and restoration notifications target
the store owner; the backend sends browser registration tokens through Firebase
Messaging and removes tokens that Firebase reports as not found.

Merchant order references open a detail dialog with store fulfillment, customer,
item and delivery information. Order notifications include a store-scoped link
that opens the matching order dialog, including when the order is outside the
current list page. Merchant order, payout and earnings-ledger detail dialogs
include a print action that formats the detail panel for printing; payout
account and routing numbers are masked in the merchant view.

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

### Product media delivery

Product cards, storefront imagery, review photos, avatars and other listing surfaces use Next.js image optimization for configured MinIO media, Unsplash and Google profile images. The optimizer serves responsive AVIF/WebP variants and a compact blurred loading placeholder; catalog cards and gallery thumbnails request display-sized derivatives at lower quality than the main detail image. Optimized images are cached for at least seven days; uploaded media uses non-overwriting storage paths, and replaced profile images receive versioned URLs. The main image in the product detail gallery and the opened media viewer keep the original source, so full-resolution bytes are requested only when the user opens the product or media itself. For Docker, `MINIO_PUBLIC_URL` is used to allow the media host at build time, while the optimizer reads MinIO through the internal `minio:9000` service name. Unconfigured third-party hosts fall back to the browser image path and are not resized by Next.js.

Preview opens `/merchant/products/preview` in a separate tab using tab-scoped draft storage. It mirrors the buyer product-detail layout with product gallery, prices, options, seller card, and digital-download label while disabling checkout, save, and seller navigation. The original editor keeps unsaved inputs and uploads. Allow pop-ups for this action; a blocked pop-up produces a visible editor error.

Product saves remember the returned product ID before uploading assets. If an upload fails, Save changes retries against that listing with PATCH. Successful uploads are cleared from the pending queue, and submissions are guarded while a save is running.

Order-status override confirmation requires a nonempty audit reason before enabling Update status. Browser tests cover this requirement and the current wallet checkout flow.

The unsaved product preview displays variant options with selectable prices and images, plus the configured flash deal countdown in the product price block. Countdown badges stay content-sized beside price details on both the preview and product detail page. Expired draft deals show an explanation instead of disappearing.

The merchant product list and CSV export include a per-product units-sold count from the owner-scoped product API. Affiliate partner products display “Not tracked” because checkout and sales happen on the external partner site.

The storefront header search submits to `/shop?search=...`; catalog search covers product title, brand, category, tags, and description through Elasticsearch with a database fallback. Queries shorter than three characters use database substring matching so partial input such as `k` can match inside product words.

Admin user profiles use a dedicated responsive two-column layout for the wallet ledger and activity timeline; the panels stack on narrow screens so profile sections do not overlap.

The API proxy expires authentication cookies on authenticated 401 responses only. Anonymous 401 responses do not clear a session created by a concurrent login.

Backoffice navigation uses a dedicated responsive icon navigation row with active-page highlighting, separate from account controls. Overview destinations appear once in the same horizontally scrollable navigation row, including merchant payouts, users, administrator commission withdrawals, and technical-admin Grafana metrics. Required admin and staff password changes use a focused security card with password confirmation and a visibility toggle.

Store onboarding requires a complete business address (street, city, state/region, country and postal code). Products may be saved as drafts, but manual and scheduled publication require that address for both digital and physical listings.

Time handling: Django stores timezone-aware UTC instants (`TIME_ZONE=UTC`, `USE_TZ=True`). Browser date/time inputs display local time and submit ISO UTC timestamps. Dashboard requests accept a validated IANA `time_zone` (UTC by default); the browser supplies its timezone for local calendar-day reporting. Date-only chart labels are preserved without timezone shifts. Cron and carrier request clocks use aware UTC; flash countdowns include minutes.

Military postal delivery: APO/FPO/DPO destinations use USPS only with the currently supported integrations. Checkout disables other carrier options and the server rejects unsupported carriers in both demo and live rating and payment flows. Address city/state/ZIP must agree: AA uses 340xx, AE uses 090xx–098xx, AP uses 962xx–966xx, with country United States. This is a supported-service policy, not a claim that all commercial postal handoff services are prohibited: UPS Ground Saver and Mail Innovations have military-address support but are not integrated here. See [USPS military addressing standards](https://pe.usps.com/text/dmm300/703.htm) and [UPS supported services](https://www.ups.com/us/en/support/shipping-support/print-shipping-labels/how-to-write-address). ZIP blocks alone do not guarantee an active destination or eligibility for every USPS service; live carrier availability and military mail content/customs requirements still apply.

Cart mutations submit an optional `variant` option name alongside product and quantity, and rendered cart products expose `selected_variant`. Every product with options also shows a selectable **Original edition** choice that uses the main price, stock, image, and digital asset; distinct options have separate cart rows. Guest cart and saved-item entries that fail to merge at sign-in remain persisted for review and retry. CSV imports limit files to 2 MB / 500 rows, reject ambiguous numeric price formats and show failed row numbers. The same-origin proxy deduplicates refresh calls, preserves sessions during upstream outages and sets access-cookie lifetime from the upstream JWT expiry. See [audit remediation](security-audit-remediation.md) for verification and operational boundaries.

On product detail pages, the quantity selector is the desired total for that product and variant in the bag. The action stays disabled when that total already matches the bag, adds the difference when it increases, and updates the bag when it decreases. Its maximum is the available stock. Digital products remain limited to one cart entitlement.

## ClickBank Partner Storefront & Editor Experience

- **Catalog & Cards**: Products configured as `affiliate_clickbank` render distinctive orange "Partner Offer" and "ClickBank" badges on product cards. The "Add to bag" action is replaced by a direct outbound tracking anchor (`/api/affiliates/clickbank/outbound/${product.id}`) opening in a secure new tab (`target="_blank"`, `rel="noopener noreferrer"`).
- **Product Detail**: Detail pages replace local quantity selectors and stock countdowns with an "Official Partner Listing · In Stock" notice and a partner delivery card indicating fulfillment by ClickBank and the partner vendor.
- **Merchant Product Editor**: The editor provides a Listing Type selector (`standard` vs `affiliate_clickbank`). Choosing affiliate displays a configuration panel for HopLink URL, vendor nickname, and custom CTA button text, while locking platform discounts to 0%, omitting flash sale timers, and displaying partner pricing notices to prevent fictitious pricing discrepancies. Physical shipping dimensions and variant tables are also bypassed.
- **Backoffice Catalog Audit**: Staff users can filter listings by "ClickBank affiliate offer", view partner offer badges, inspect outbound HopLinks, see tracked units sold for standard products, and open each product in read-only preview from the store audit table. Partner offer sales are completed externally and are labeled as not tracked. Coupon creation is strictly disallowed for ClickBank products because checkout is completed externally.
- **Store Detail**: Business and technical administrators can suspend or reactivate a merchant store from its detail page. Initial store loading is centered over the viewport; catalog refresh loading stays in the catalog flow.

## October commerce audit fixes

Checkout shipping/tax previews include the applied coupon in their query and cache key. Account refund actions require remaining settled funds; cancellation requires every store shipment to remain unfulfilled. Order DTOs expose paid/refunded totals, allocated line amounts, and store fulfillments. Backoffice customer orders (`/admin/orders`) provide multi-dimensional filtering across order lifecycle status, payment tender, and delivery courier (USPS, UPS, FedEx, DHL Express, and Digital) with instant reset and carrier search integration. Generated affiliate URLs enter the same-origin `/api/affiliates/r/` proxy.

Store settings use plain customer-facing labels for store branding, the logo URL, cover image URL, and store announcement. Design references are kept out of the settings interface. Merchants can pin up to 3 featured products to appear at the very top of their public storefront page (`/shop?store=<id>`), managed through 3 dedicated slots in `/merchant/settings` or via the one-click Pin toggle in the merchant products catalog table. Pinned products display high-contrast dual-theme `Pinned` badges on their product cards.

## User Profile Photo & Avatar Management

- **Universal User Avatar Support**: User avatars are rendered across all customer, merchant, and administrative views: header account dropdown trigger, account menu, personal details page (`/account?section=profile`), merchant workspace sidebar footer, and staff/admin audit tables.
- **Interactive Avatar Cropper (`UserAvatarUpload` & `UserAvatarCropDialog`)**: Provides client-side circular crop preview with zoom, pan, and real-time canvas rendering to guarantee standard 512x512 JPEG export conforming to server constraints, managed centrally under Personal Details (`/account/profile`).
- **App Settings & Email Communication Preferences**: The global `/settings` interface provides application appearance toggles (Light / Dark / System). For authenticated users, it dynamically renders an **Email communication preferences** section allowing users to toggle optional emails for **Product recommendations** and **Marketing & promotions** via `PATCH /api/v1/me/`, while preserving mandatory transactional receipts and shipping alerts.
- **Backoffice Profile Isolation**: When administrative users (staff, superadmins, business admins) access `/account` or `/account/profile`, consumer-specific widgets (orders, wallets, addresses, and saved items) and queries are completely excluded. Backoffice users are presented with their personal details (name, email, phone, password management, avatar studio) and quick links to backoffice tools, while shopper-only routes (`/account/orders`, `/account/wallet`, `/account/addresses`) redirect them safely.

ClickBank offer prices are retained only as internal catalog references. Public product cards, detail pages, and listing previews direct shoppers to check the current price on the partner site. Selecting the ClickBank listing type hides ProAce discount and flash-deal controls; the server rejects those promotions and clears them when converting a standard listing.

Store profile pages (`/shop?store=<id>`) list only that store’s products. Filter resets retain the store and any `preview=1` mode; previews remain read-only.

The catalog supports 29 departments shared by homepage category tiles, shop/store filters, and merchant product forms: Electronics, Fashion, Phones, Computing, Sports & outdoors, Books, Toys & games, Kids & baby, Home & living, Kitchen & dining, Beauty & personal care, Health & wellness, Pet supplies, Gaming, Tablets, Fishing, Lingerie & sleepwear, Coffee, tea & drinks, Garden & tools, Automotive, Jewelry & watches, Software & apps, Courses & learning, Templates & planners, Design assets, Photos & video, Music & audio, Business resources, Digital tools & presets. New department keys are validated by Django product choices; apply product migrations before using them. Existing product category keys are preserved.

Backoffice user profiles use a compact identity card with contact and activity details, three financial summary cards, and bordered wallet, activity, and order panels. The layout stacks on smaller screens and respects the active theme.

Every digital product can have an uploaded downloadable file per variant. Merchants declare each option as Image, Audio, Video, or Document/software before upload; the server enforces that the file matches the declared option type. Digital-artwork gallery uploads and image variants are converted into watermarked carousel previews, while original downloads remain private until an authorized purchase. Completed orders use the file mapped to the option purchased.

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

Collection refreshes use the shared compact spinner across storefront search, seller workspaces, backoffice listings, store management, and notifications. The spinner preserves the existing results and controls while data is fetching, and announces “Updating results” to assistive technology without showing that text in the interface.

The referral workspace at `/account/affiliates` supports enrollment, copyable `/register?ref=…` invite links, credited-signup progress, and searchable/filterable paginated referral history. Registration accepts an invite code visibly in an optional field; referral attribution is recorded upon email verification, while rewards are issued only when a referred user completes their first successful order to prevent throwaway account abuse. The server grants $25 non-withdrawable ProAce Wallet credit for up to four referred customer orders; additional referrals remain pending without credit, and reward issuance is serialized per affiliate to enforce the cap under concurrent checkouts. The displayed earned total is cumulative promotional credit, not a cash balance or ClickBank commission. `/admin/affiliates` lets backoffice operators search/filter enrolled affiliates and review referral totals, credit earned, qualifying orders, and account status, with links to existing user management. Customer history omits referred users’ personal information; affiliate account, wallet, and referral routes reject backoffice accounts. Generated links can only target published products in active, verified stores and stop redirecting if a listing becomes unavailable. API endpoints: `/api/v1/affiliates/workspace/` (owner-scoped), `/api/v1/affiliates/referrals/` (owner-scoped, paginated), and `/api/v1/admin/affiliates/` (backoffice-only).

Digital product onboarding & variant enhancements:
- **Auto-Cover & Smart Photography Card**: When onboarding digital image assets (artwork, wallpapers, photography), the uploaded file immediately populates the storefront cover preview. The Product photography section shows an auto-generated cover card with a `PROACE PREVIEW` badge indicating that no separate cover photo is needed, while preserving an optional upload button for custom promotional banners.
- **Storefront Carousel & Watermark Integration**: On the public storefront and in live merchant preview, digital image previews display the `PROACE PREVIEW` watermark overlay across all gallery and variant images.
- **Digital Options & Variants**: Digital products support edition/resolution variants (e.g. 4K Wallpaper, Mobile HD, Print-Ready Vector). The variant editor displays an "Unlimited digital inventory" badge instead of physical stock counters, permits price adjustments, and syncs variant selection with image switching in the gallery carousel.


Product-page interaction hooks, including share-link feedback state, are initialized before loading/error returns. This keeps hook order stable when asynchronous catalog data arrives and prevents the product page from crashing during guest browsing and checkout.

The backoffice overview shows pending merchant payouts, recent requests with detail dialogs, and the affiliate/referral board directly below the summary cards. Payout details remain available for pending, completed, and rejected requests. Authorized staff, business administrators, and technical administrators can inspect, complete, or decline pending requests from the list or details dialog. Account and routing numbers show only their first two and last two characters; legacy last-four-only values show only their final two characters. Approval initiates a Stripe Connect transfer. Bank transfers are sent outside the app and must be confirmed before marking the request completed.

Store creation includes optional store profile picture and Store label (banner/cover) uploads with cropping and previews. JPEG, PNG, and WebP images up to 5 MB use the existing protected branding endpoints after the store is created. Failed image uploads can be retried without creating another store. Creating an additional store selects it before opening the first-product editor. Creating a merchant's first store also initializes their unified merchant wallet in the same transaction; later stores share it. Stripe Express account IDs are committed before onboarding-link creation, so a temporary link failure can be retried against the same account.

Social signup imports a missing Google profile image from the verified credential into configured media storage (MinIO/S3 when enabled), preserving user-selected avatars. When tokeninfo omits the picture, the accepted ID token supplies that claim after provider verification. Google/Apple sign-in with an empty phone number prompts for a phone number and saves it through the authenticated profile endpoint before continuing; existing phones are preserved. Referral codes from the signup field, URL or remembered auth-page referral remain attached to new social signups only; existing-account logins do not create or reassign referrals. A missing Google image or unavailable image service does not block authentication and is retried on the next sign-in while the avatar remains empty.

Logout immediately aborts pending browser API requests and cancels account queries before push cleanup or server revocation. The proxy propagates browser cancellation to backend and refresh requests, preventing a late token-refresh response from restoring auth cookies. Logout expires both root-path auth cookies, updates the observed session query to an anonymous value, and removes other cached account data without detaching the session observer. Unauthorized profile responses clear the displayed identity instead of retaining a previous signed-in greeting.

Customers can manage Google/Apple connections and password sign-in in profile/settings. Provider subjects resolve to a single account, verified matching emails link existing customer profiles, and disconnect preserves at least one login method. See [social account linking](social-account-linking.md) for the schema, authenticated API routes, legacy account migration, security rules and frontend flow.

Settings use compact expandable sections for appearance, browser alerts, optional email preferences and sign-in methods. Browser alert setup waits for the registered Firebase service worker to become active before requesting the device token; the settings page and notification menu share this flow. Authentication pages remain viewable while signed in, with email/password above horizontal Google/Apple alternatives. Sign-in and registration controls are disabled during session loading or an active session; an explicit sign-out action permits account switching. The backend rejects login, registration and public social sign-in attempts carrying a valid current session with HTTP 409, while expired/revoked credentials can recover through normal sign-in. Existing authentication throttling remains active. Password recovery and authenticated provider linking remain available.

Treasury destination selectors keep bank and Stripe account management available even when no default is selected or no accounts are saved. Choose account opens the selector; empty states stay inside it, with compact add/manage actions and edit/default/delete controls for saved accounts.

Treasury withdrawal references expose a hover/focus summary and open a printable details dialog. The Payout accounts page uses explicit default badges and compact per-account Actions menus for editing, deleting, and setting the default.

Saved bank and Stripe account lists share a compact filtering toolbar: debounced search with field-specific placeholders, default-account selection, recent/name sorting, matched counts, and a conditional Clear filters action. Filtering uses the complete owner-scoped saved collection.

Payout account actions prevent overlapping mutations and report successful default/deletion changes. Pickers discard selections that disappear from refreshed account lists. Unified merchant payout history applies search, status, method, date and amount criteria before pagination, with deterministic creation/ID ordering.

Open payout-account Actions menus layer above neighboring account controls so Edit/Delete/Set default remain clickable in multi-account lists.

Merchant payout requests use the treasury-style compact amount/note form and shared bank destination picker. Change/Choose account opens the saved-account management popup instead of embedding full account cards in the withdrawal form. Saved bank accounts are user-provided destinations, not independently bank-verified accounts.

Store dashboards expose `withdrawable_balance`, capped by both the store’s cleared funds and the unified wallet after pending/completed payouts. Merchant payout controls use that amount. Repeated fake-data seeding preserves existing payout debits and does not generate another automated demo payout for the same wallet.


### Notification record navigation

Notification actions use recipient-scoped destinations and contextual labels for orders,
refunds, payouts, stores, wallet, referrals, and account notices. Admin orders/refunds/payouts
and merchant payouts/earnings consume `order`, `refund`, `payout`, or `ledger` query IDs to
open their existing detail dialogs. Buyer orders retain their dedicated detail page;
stores/accounts/wallet/referrals open their existing relevant page. Closing a notification
dialog clears its record query parameter. Unavailable records show a clean access/unavailable
message and leave the listing usable.

Dialog resolution uses a separate, user-keyed request with `record_id`, `limit=1`, and
`offset=0`, independent of listing search, filters, and pagination. `record_id` is a positive
integer accepted by shared filtered listing endpoints and admin order/refund listings;
existing endpoint permissions and tenant ownership still apply. Saved notification payloads
are resolved through the current routing policy when serialized and when push is dispatched,
so legacy list-only URLs do not require database reseeding or a notification resend.


### Backoffice store order history

`/admin/stores/<id>` includes a Store orders section with independent debounced
search, status/carrier/payment filters, sorting, reset, counts, pagination and the
existing order detail dialog. The shared admin order endpoint accepts a positive
`store_id` and filters before pagination. Immutable item snapshots define store
membership, with fulfillment associations and an empty-snapshot legacy cart fallback.
Mixed orders appear for each participating store; displayed totals and emergency
status actions apply to the complete customer order, as labeled. Migration
`payment.0021_order_items_store_gin` adds a PostgreSQL GIN index for snapshot store
membership (SQLite uses its test-compatible index implementation). Existing backoffice
permissions apply; this does not grant access to third-party merchant dashboards.


### Backoffice store payments

Admin store detail pages include store financial totals, payout history and an earnings
ledger with detail dialogs. The summary uses the existing store financial calculation;
filters apply to histories independently of the all-time summary. Each history has its
own debounced search, status/type/method/date/amount filters, reset, count and pagination.
`GET /api/v1/admin/staff/stores/<id>/financials/` returns the typed financial summary;
`GET /api/v1/admin/staff/stores/<id>/ledger/` returns filtered, paginated store ledger
entries. The existing `/api/v1/admin/staff/payouts/?store_id=<id>` endpoint scopes payout
history to that store before filtering and pagination. Unallocated merchant-wallet payouts
are not attributed to individual stores. These endpoints retain backoffice permissions
and do not grant merchant-dashboard access or submit financial transactions.


The admin dashboard Refund operations preview uses a full-width, horizontally scrollable
refund table: refund/order links open their detail dialogs, with customer, amount, method,
status, reason, created date and existing approve/decline actions in separate columns.
The preview retains the latest five requests; View all refunds opens the searchable,
filterable full history. Styling uses shared table, button and status primitives in both themes.


The dashboard operations previews are stacked at full width: Refund operations first,
then Coupon operations. Coupons use a scrollable table with code/detail link, discount,
usage, status, validity dates, creator email and existing toggle/delete controls.
Used-coupon deletion protection and the full searchable coupon history are unchanged.
Backoffice refund listings (overview and full history) and refund detail dialogs show the processing staff or administrator's email under “Processed by” after an action. Attribution comes from the backend's recorded refund processor; pending or older records without a processor show no invented identity. This field is exposed only through the existing backoffice refund serializer and access controls.
App-wide audit fixes (2026-10-15): merchant order history resolves recorded snapshot/fulfillment membership, with live-cart fallback for legacy records. Merchant shipment events are store-scoped; delivery addresses appear only for that store's physical items. Digital download links include an encoded `variant` selector when required and resolve only purchased order lines; legacy single-item links remain supported. Guest physical carts display “Calculated at checkout” and keep totals limited to item costs until the backend quotes delivery. Failed refund attempts retain the operator email, timestamp and reason, while customer/backoffice payloads use safe failure text, including for older failed records. Malformed password-reset identifiers return validation errors. The security runner requires expected live response statuses, uses the current protected routes, treats unreachable probes as failures and exits nonzero on failure. Run `.venv/bin/pytest scripts/qa/test_security_reports.py` for offline runner regressions in addition to the standard test suites.
The security runner, its offline regression tests and shared report helper are explicitly exempted from the local `scripts/` ignore rule so their fixes can be versioned; generated `qa-reports/` output remains ignored.


Checkout address dialogs use the shared address form in embedded mode, without a
second card or repeated heading. Address rows share label/input/error tracks to keep
controls aligned when labels or validation messages wrap, and stack on narrow screens.
Standalone address forms retain their heading and card; both modes use theme tokens.

## Proxy request diagnostics

Only the exact notification-stream route can target `NOTIFICATION_STREAM_URL`; all other routes, including token refresh, use `API_URL`. Refresh deduplication is keyed to the main authentication API even when the triggering request was a stream, preventing concurrent stream/ordinary refresh races. Browser URLs and HttpOnly cookies are unchanged. Compose configures the dedicated internal service through `CONTAINER_NOTIFICATION_STREAM_URL`; leave the optional local-development stream URL blank for the original single-process workflow. An unavailable configured stream process does not fall back to the ordinary API.

The same-origin API proxy preserves only validated `X-Request-ID`, `X-Catalog-Cache` and numeric `Server-Timing` fields from Django. Its additional `proxy` duration includes backend wait and response preparation; it is not proxy-only overhead. Authentication cookies, token isolation and `Cache-Control: no-store` remain unchanged. Arbitrary upstream headers are not forwarded. See [performance](performance.md) for timing boundaries.


Signed-out visitors to `/orders/<id>` are redirected to `/login?next=...` after the
session check, then returned to that order after authentication. A signed-in viewer
without access sees an unavailable-order message with Your orders and an explicit
Switch account action. Switching uses normal logout before opening sign-in and retains
the order return path. Missing and inaccessible orders share the same safe 404 response;
no owner identity is revealed. Expired-session 401s return to sign-in, while other order
loading failures show a generic retry message without exposing backend internals.

The customer order detail header centers the order status above the Print receipt action, with consistent spacing on desktop and mobile.

Order refund forms use compact item rows with separate titles, quantities and amounts, theme-aware separators, and wrapping actions. The shopping action is hidden while a refund request is being edited.

## Merchant Product Refunds Workspace (`/merchant/refunds`)

Merchants can inspect customer return and refund activity for their store at `/merchant/refunds`.
- **Navigation & Routing**: Accessed via the Seller workspace sidebar under "Refunds" (`RotateCcw` icon). Supported dynamically through the Next.js catch-all router with store switcher support (`?store=<id>`).
- **Product-Level Scoping**: Unlike backoffice order-level refunds, the merchant listing scopes refunded items, counts, and amounts specifically to products belonging to the active store. For mixed-cart orders, merchants see only their store's refunded line items and store refund total, preventing exposure of other vendors' items.
- **Universal Search & Multi-Criteria Filtering**: Debounced search across refund #, order reference, customer email, product title, and return reasons. Orthogonal filters for status (`pending`, `approved`, `declined`, `failed`), refund method (`store_credit`, `original_payment`), timeframe (`Last 7 days`, `Last 30 days`, `Last 90 days`, `All time`), and sort order (`Newest first`, `Oldest first`, `Highest amount`, `Lowest amount`), with single-click "Reset filters" and live active filter indicators.
- **Accessible Detail Dialog**: Accessible modal (`RefundDetailDialog`) with keyboard trapping and background dismissal. Shows customer email and name, order reference link, refund method, store refund amount, total order refund amount, request/processed timestamps, customer return reasons, staff moderation decision notes, and product table with thumbnails, titles, variant metadata, quantities, and line totals.
- **Deep-Linking & Notifications**: Deep linking supported via `?refund=<id>`: auto-opens the refund detail modal, and clears the query parameter on modal dismissal without page reload. Merchant refund notifications route directly to `/merchant/refunds?store=<id>&refund=<id>` with action label "View refund".

