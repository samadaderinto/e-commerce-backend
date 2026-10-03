# Proace Commerce client

This is the Next.js frontend for the Proace marketplace. It lives in the same
repository as the Django backend, but it is designed to be hosted separately.

## Backend bridge

Browser code calls the local Next.js proxy at `/api/*`. The proxy is implemented
in `client/src/app/api/[...path]/route.ts` and forwards requests to the backend
API configured by `API_URL`.

Local container-friendly default:

```env
API_URL=http://host.docker.internal:8000/api/v1
```

Production should set `API_URL` to the deployed backend API, for example the
backend URL ending in `/api/v1`; production uses the private Docker address
`http://api:8000/api/v1` on HostGator.

The proxy keeps access and refresh tokens in HTTP-only cookies, refreshes expired
access tokens, hides raw tokens from browser JSON responses, and enforces
same-origin checks for mutating browser requests.

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

From `client/`:

```sh
npm run dev
npm run build
npm run start
```

## Container

Build and run the frontend container from the repository root:

```sh
docker compose -f client/compose.yaml up --build -d
```

The container listens on `127.0.0.1:3000` by default and reads `API_URL` from
`client/.env`, falling back to `http://host.docker.internal:8000/api/v1`.

## Documentation

Frontend documentation lives in [`../docs/frontend.md`](../docs/frontend.md).
Update it whenever frontend routing, proxy behavior, client deployment, or frontend
tests change.
