# Backend bridge

The frontend does not call Django directly from browser components. It calls
same-origin `/api/*` routes in Next.js, and the proxy forwards to the Django API
configured by `API_URL`.

## Request path

```text
Browser component
  -> client/src/lib/api.ts
  -> /api/*
  -> client/src/app/api/[...path]/route.ts
  -> API_URL on the Django backend
```

## Auth handling

- Login responses set `proace_access` and `proace_refresh` HTTP-only cookies.
- Browser JSON responses do not expose raw tokens.
- Non-auth API calls retry once after refreshing an expired access token.
- Logout clears both cookies.
- Mutating requests require a same-origin `Origin` header.

## Production bridge

When the backend is hosted on Render and the frontend is hosted elsewhere, set the
frontend host's `API_URL` environment variable to:

```env
API_URL=https://your-render-backend.example.com/api/v1
```

For the local frontend container on Docker Desktop, use:

```env
API_URL=http://host.docker.internal:8000/api/v1
```

The backend must set `FRONTEND_URL` to the deployed frontend origin so generated
email links and origin-aware flows point to the right site.
