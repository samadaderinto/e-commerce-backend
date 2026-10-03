# Frontend documentation

The frontend lives in `client/` and is a Next.js App Router application using
TypeScript, React 19, React Query and shared UI components.

## Code map

- `client/src/app/layout.tsx`: app shell root, global metadata and providers.
- `client/src/app/[[...slug]]/page.tsx`: catch-all page router for storefront,
  account, merchant, admin, and help views.
- `client/src/app/api/*`: same-origin API proxy routes that talk to Django.
- `client/src/components/shell.tsx`: shared navigation, search bar, and layout shell.
- `client/src/components/storefront.tsx`: catalog, product detail with selectable variant chips,
  photo review gallery with lightbox, flash deal countdowns, store profiles with marquee announcements,
  and quick "Message Store" customer action.
- `client/src/components/cart.tsx`: cart and multi-method checkout UI (COD, ProAce Wallet, Stripe).
- `client/src/components/account.tsx`: auth, profile, addresses, ProAce Wallet ledger,
  order details with live USPS package tracking, and 7-day refund submission form.
- `client/src/components/merchant.tsx`: seller onboarding, dashboard with milestone celebration banners,
  product editor with variant option configuration, bulk CSV catalog importer, 7-day escrow financial breakdown,
  4% platform fee calculation, payout requests, inventory health, and order fulfillment modal.
- `client/src/components/admin.tsx`: `AdminDashboardPage` (platform-wide business insights,
  order fulfillment distribution bar chart, store leaderboards) and `AdminStaffPage`
  (staff account creation, permission controls, and blocking).
- `client/src/components/ui.tsx`: reusable controls, product cards, `VerifiedBadge` (seller rank tier icons),
  `FlashCountdown` (real-time sale expiration timer), loading spinners, and small primitives.
- `client/src/lib/api.ts`: browser API helper, error normalization, money
  formatting and category constants.
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
- hiding raw token values from browser-visible JSON responses;
- enforcing same-origin behavior for browser mutations.

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
