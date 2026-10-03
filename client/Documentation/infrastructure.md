# Client infrastructure

The frontend can run locally with Node or as its own container. It is intentionally
separate from the backend container so it can be hosted on a frontend platform
while the backend runs on the same HostGator VPS private Docker network.

## Files

- `Dockerfile`: builds a standalone Next.js runtime image.
- `compose.yaml`: local frontend container runner.
- `.dockerignore`: client-local ignore file.
- `../.dockerignore`: root Docker ignore file used by the frontend build context.
- `next.config.ts`: security headers and `output: 'standalone'`.
- `.env`: local frontend env, ignored by Git.
- `.env.example`: tracked frontend env template.

## Local container

From the repository root:

```sh
docker compose -f client/compose.yaml up --build -d
```

Defaults:

- host: `127.0.0.1:3000`;
- backend API: `API_URL` from `client/.env`, falling back to
  `http://host.docker.internal:8000/api/v1`.

For production frontend hosting, set `API_URL` in that platform's environment
settings. Do not commit production env files.
