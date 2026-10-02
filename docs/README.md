# Proace Commerce documentation

This directory is the code documentation hub for the whole project. Keep it
updated whenever frontend, backend, deployment, or observability behavior changes.

## New here?

Start with the [getting-started guide](getting-started.md) to set up the
development environment and run the apps. Then read the
[architecture and API map](architecture.md) to understand the request flow,
backend entry points, and current design boundaries. Use the focused guides
below when you need implementation or operational detail.

## Documentation map

- [Getting started](getting-started.md): prerequisites, local setup, configuration, tests and common commands.
- [Architecture and API map](architecture.md): repository layout, runtime flow, endpoint groups and current design decisions.
- [Frontend](frontend.md): Next.js structure, routing, API proxy, state, tests and UI conventions.
- [Backend](backend.md): Django structure, API apps, authentication, caching, storage, tests and admin/runtime notes.
- [Infrastructure](infrastructure.md): Docker Compose, PostgreSQL, Redis, Kafka/RabbitMQ, Nginx, object storage and production boundaries.
- [Observability](observability.md): health checks, metrics, p95/p99 latency, logs, traces, profiling and dashboards.

For feature-specific behavior and safeguards, also see the
[root README](../README.md). It describes the implemented customer and seller
workflows and calls out what is not production-ready.

Frontend-local documentation:

- [Client docs](../client/Documentation/README.md): frontend bridge, frontend container and client hosting.

The pages in this `docs/` directory are the canonical backend and cross-project
guides. Avoid maintaining a second, conflicting copy of the same setup or
architecture instructions.

## Monorepo shape

```text
e-commerce-backend/
  client/
    src/app/              Next.js routes and API proxy
    src/components/       Storefront, cart, account and merchant UI
    src/lib/              Browser API helper and shared types
  server/
    codematics/           Django settings package; active and legacy settings
    storefront/           Integrated API URL configuration and views
    core, product, store/
    cart, payment, notification/
    affiliates, staff, observability/
    compose.yaml          API and data-service containers
    monitoring/           Prometheus, Grafana, Loki, Alloy and Tempo
  docs/                   Canonical cross-project documentation
  .github/workflows/      CI, security checks and Render deployment
```

The frontend and backend share one repository but are deployable separately. The
frontend host sets `API_URL` to the backend `/api/v1` URL. The backend deploys to
Render and receives production configuration from GitHub Actions secrets. See
[Architecture and API map](architecture.md) before changing how those apps
communicate.

## Update rule

When code changes, update the matching document in the same pass:

- Frontend routes, components, client API calls or tests: update `docs/frontend.md`.
- Django apps, serializers, views, models, auth, permissions or tests: update `docs/backend.md`.
- Compose, Dockerfile, Nginx, PostgreSQL, Redis, Kafka, RabbitMQ or storage: update `docs/infrastructure.md`.
- Changes to API boundaries, runtime selection or design constraints: update `docs/architecture.md`.
- Deployment workflow or production secrets: keep `server/deployment.md` and the infrastructure guide aligned.
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
