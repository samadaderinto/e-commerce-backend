# Frontend

The client is a Next.js App Router app with TypeScript, React 19, React Query,
Playwright tests and shared UI components.

## Key paths

- `src/app/layout.tsx`: root layout and providers.
- `src/app/[[...slug]]/page.tsx`: catch-all app route for storefront, account,
  merchant and help views.
- `src/app/api/[...path]/route.ts`: backend proxy.
- `src/components/storefront.tsx`: catalog and product detail UI.
- `src/components/cart.tsx`: cart and checkout UI.
- `src/components/account.tsx`: auth, profile, addresses and order history.
- `src/components/merchant.tsx`: seller workspace.
- `src/components/ui.tsx`: shared controls.
- `src/lib/api.ts`: browser API helper and error normalization.
- `src/lib/types.ts`: shared frontend DTOs.

## Config

| Variable | Purpose |
| --- | --- |
| `API_URL` | Backend API base URL used by the Next.js proxy |
| `E2E_BASE_URL` | Playwright base URL |
| `E2E_DEMO_PASSWORD` | Seed-account password for e2e tests |
| `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH` | Optional local browser path |
| `NEXT_PUBLIC_FIREBASE_*` | Public Firebase Web app config and VAPID key for optional browser push |

Use `client/.env` locally and `client/.env.example` as the tracked template.

## Notifications

The notification center reads the authenticated `/api/v1/notifications/` inbox.
Optional FCM browser alerts supplement the inbox: configure the `NEXT_PUBLIC_FIREBASE_*`
values from the Firebase Web app, enable Firebase Messaging and a Web Push certificate,
then enable FCM on the backend. Users opt in through the notification panel; the
authenticated `/api/v1/notifications/devices/` endpoint registers and removes their
browser token. The service worker checks the current session before displaying a push.

## Commands

```sh
npm run dev
npm run build
npm run start
npm run typecheck
npm run test:unit
npm run test:integration
npm run test:e2e
```
