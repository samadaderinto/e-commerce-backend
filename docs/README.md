# Proace Commerce documentation

This directory is the code documentation hub for the whole project. Keep it
updated whenever frontend, backend, deployment, or observability behavior changes.

## Documentation map

- [Frontend](frontend.md): Next.js structure, routing, API proxy, state, tests and UI conventions.
- [Backend](backend.md): Django structure, API apps, authentication, caching, storage, tests and admin/runtime notes.
- [Infrastructure](infrastructure.md): Docker Compose, PostgreSQL, Redis, Kafka/RabbitMQ, Nginx, object storage and production boundaries.
- [Observability](observability.md): health checks, metrics, p95/p99 latency, logs, traces, profiling and dashboards.

## Update rule

When code changes, update the matching document in the same pass:

- Frontend routes, components, client API calls or tests: update `docs/frontend.md`.
- Django apps, serializers, views, models, auth, permissions or tests: update `docs/backend.md`.
- Compose, Dockerfile, Nginx, PostgreSQL, Redis, Kafka, RabbitMQ, storage or deployment: update `docs/infrastructure.md`.
- Health endpoints, logging, metrics, alerts, tracing, profiling, Grafana, Loki, Prometheus, Tempo or Alloy: update `docs/observability.md`.
- Cross-cutting changes should update more than one document when needed.

Do not treat this directory as marketing copy. It should describe how the code
actually works today, where to look, how to run it, and what risks or boundaries
still exist.

## Environment policy

Keep environment files simple:

- `server/.env`: local server, Compose and monitoring values. Ignored by Git.
- `server/.env.example`: tracked server template.
- `client/.env`: local frontend values. Ignored by Git.
- `client/.env.example`: tracked frontend template.

Do not add `.env.prod`, per-service env files, or hidden env files under
`server/monitoring/`. Production values belong in GitHub Actions secrets or the
deployment platform secret manager. For Render, the CD workflow syncs GitHub
Actions secrets to Render service environment variables before triggering the
Render deploy hook.
