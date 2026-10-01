# Frontend bridge

The backend is consumed by the Next.js client through the client's same-origin
proxy. Browser components call `/api/*`; the proxy forwards to Django.

## Backend values that must match frontend hosting

| Backend variable | Purpose |
| --- | --- |
| `FRONTEND_URL` | Public frontend origin for email links and browser flows |
| `ALLOWED_HOSTS` | Backend hostnames accepted by Django |
| `OBSERVABILITY_TOKEN` | Protects `/metrics/` and detailed health |

When the frontend is hosted separately, update `FRONTEND_URL` in Render to the
frontend deployment URL. The frontend host must set `API_URL` to the Render
backend URL ending in `/api/v1`.
