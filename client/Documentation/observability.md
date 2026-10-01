# Client observability

The frontend currently relies on platform logs and backend observability. The
Next.js proxy is the main bridge point to watch because it converts browser
requests into backend API calls.

## What to inspect

- Frontend host logs for Next.js render/proxy errors.
- Browser network tab for `/api/*` requests.
- Backend Loki logs with `{service_name="api"}` for the request that reached
  Django.
- Backend metrics and traces for API latency, errors and dependency state.

## Proxy failure behavior

If the backend cannot be reached, the proxy returns:

```json
{"detail":"The shop is temporarily unavailable. Please try again shortly."}
```

with status `503`.

When frontend hosting adds its own monitoring, document it here: uptime checks,
web vitals, error tracking, CDN/cache behavior and deployment logs.
