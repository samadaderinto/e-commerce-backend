# Frontend documentation

The frontend lives in `client/` and is a Next.js App Router application using
TypeScript, React 19, React Query and shared UI components.

## Code map

- `client/src/app/layout.tsx`: app shell root, global metadata and providers.
- `client/src/app/[[...slug]]/page.tsx`: catch-all page router for storefront,
  account, merchant and help views.
- `client/src/app/api/*`: same-origin API proxy routes that talk to Django.
- `client/src/components/shell.tsx`: shared navigation and layout shell.
- `client/src/components/storefront.tsx`: catalog, product detail and shopping
  storefront views.
- `client/src/components/cart.tsx`: cart and checkout UI.
- `client/src/components/account.tsx`: auth, profile, addresses and orders UI.
- `client/src/components/merchant.tsx`: seller onboarding, dashboard, products,
  orders and store settings.
- `client/src/components/ui.tsx`: reusable controls and small primitives.
- `client/src/lib/api.ts`: browser API helper, error normalization, money
  formatting and category constants.
- `client/src/lib/types.ts`: shared frontend DTO and domain types.
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

## UI conventions

- Keep user workflows directly usable from the first screen; avoid replacing app
  views with marketing-only pages.
- Use shared controls from `client/src/components/ui.tsx` before creating new
  one-off controls.
- Keep loading, empty and error states close to the feature that owns them.
- Keep forms explicit about validation and server errors.
- Use `money()` for NGN formatting so catalog, cart and order totals stay
  consistent.

## Local commands

From the repository root:

```sh
npm ci
npm run dev
npm run build
npm run typecheck
npm run test:unit
npm run test:integration
npm run test:e2e
```

The development app runs at `http://127.0.0.1:3000`. The frontend defaults to
the Django API at `http://127.0.0.1:8000/api/v1`; override `API_URL` in
`client/.env` when needed. `client/.env.example` is the tracked template.

Integration and e2e tests expect the backend and frontend to be running and the
demo accounts to exist.

## Documentation maintenance

Update this file when changing frontend routing, app structure, major components,
browser API behavior, auth-cookie behavior, UI conventions or frontend tests.
