# Getting started

This guide takes a new contributor from a checkout to a running local
marketplace. The root [README](../README.md) has a fuller walkthrough of the
container stack and implemented workflows; the linked guides below are the
reference for individual app behavior.

## Prerequisites

- Git
- Node.js 22 and npm
- Python 3.11 or newer
- Docker Desktop only if you want the container setup

The frontend is an npm workspace rooted at the repository root. The Python
virtual environment is also kept at the repository root as `.venv/`.

## Run directly on your machine

From the repository root:

```sh
npm ci
python3 -m venv .venv
.venv/bin/python -m pip install -r server/requirements.txt
.venv/bin/python server/manage.py migrate
.venv/bin/python server/manage.py populate_fake_data --password 'ProaceDemo2026!'
```

The active settings default to SQLite for a direct local run, so this path does
not require a database container. Run Django and Next.js in separate terminals:

```sh
.venv/bin/python server/manage.py runserver 127.0.0.1:8000
```

```sh
npm run dev
```

Open <http://127.0.0.1:3000>. The client calls the Django API at
`http://127.0.0.1:8000/api/v1` by default. If you need to override it, create
`client/.env` using `client/.env.example` as a starting point and set
`API_URL=http://127.0.0.1:8000/api/v1`.

The dev password above is for local seeded accounts only. `populate_fake_data` is
refused when `DJANGO_DEBUG=false`; do not use demo credentials or template
secrets in deployed environments.

### Seeding & Demo Data
- **Authoritative Seeding (`populate_fake_data`)**: The single command to populate the local environment. It always creates all essential role profiles (`admin@proace.local`, `business-admin@proace.local`, `staff@proace.local`, `seller@proace.local`, `shopper@proace.local`) along with a full catalog, reviews, orders, and financial escrow balances.
  ```sh
  .venv/bin/python server/manage.py populate_fake_data
  ```
- **Reindexing Search (`rebuild_product_index`)**: Rebuilds the Elasticsearch catalog index (`commerce-products`).
  *(See [Backend Engineering](backend.md#management-commands--data-seeding) for full flag descriptions and Docker commands).*

Email delivery uses Resend: set
`RESEND_API_KEY` and a Resend-verified `RESEND_FROM_EMAIL` in `server/.env` when
you want local flows to send real messages. Tests use an in-memory backend and
do not send email.

## Run with containers

The backend Compose stack provides PostgreSQL, Redis and Elasticsearch; the
monitoring Compose stack is optional. The frontend can also run directly on
Node.js while the backend stack runs in containers.

Follow the root [container walkthrough](../README.md#run-the-container-stack)
for network initialization, Compose commands, exposed ports, and shutdown. Read
[Infrastructure](infrastructure.md) before changing service definitions,
volumes or environment variables.

## Configuration

Start by checking the tracked templates:

- [`server/.env.example`](../server/.env.example): Django, database, cache,
  search, email, notification and optional operations settings.
- [`client/.env.example`](../client/.env.example): backend API URL, e2e-test
  settings and optional Firebase web configuration.

For direct local development, environment files are optional; the active Django
settings use SQLite by default and the frontend has a local API URL default.
When using Compose, initialize `server/.env` as shown in the container
walkthrough: Compose needs the shared credentials and local service addresses.
The Django process reads `server/.env` when present; Next.js reads
`client/.env`. Both are ignored by Git.

Production configuration is not stored in these files. The GitHub Actions
workflow reads deployment values from Actions secrets and deploys all containers
to HostGator over SSH. Follow [deployment.md](deployment.md) for the
required secret names and deployment procedure. Never commit real credentials.

## Check your setup

These root npm scripts delegate to the client workspace:

```sh
npm run typecheck              # or npm --prefix client run typecheck
npm run test:unit
npm run build                  # or npm --prefix client run build
```

Backend test settings are isolated from the local development database. You can run the complete offline pytest suite (184 tests) directly with your virtual environment:

```sh
# Fast offline backend pytest suite (184 tests)
.venv/bin/pytest server/

# Or using Django's runner with storefront test settings
.venv/bin/python server/manage.py test storefront --settings=codematics.storefront_settings --noinput
```

The integration and browser tests require the API (`python server/manage.py runserver 127.0.0.1:8000`) and frontend (`npm run dev`) to be running with seeded demo accounts (`manage.py populate_fake_data`):

```sh
npm run test:integration
npm run test:e2e
```

The test settings use SQLite, in-memory email and media, and a local-memory
cache so tests do not need production services.

## Where to go next

- [Architecture and API map](architecture.md): request flow, Django app
  responsibilities, API groups and design boundaries.
- [Frontend](frontend.md): App Router, components, browser API helper and proxy.
- [Backend](backend.md): Django implementation, runtime configuration, search
  and server-side behavior.
- [Infrastructure](infrastructure.md): containers and service configuration.
- [Observability](observability.md): health, metrics, logs, traces and local
  dashboards.
- [Root README](../README.md): product capabilities, sample accounts and
  current limitations.

## Back-office and carrier checkout

See [role matrix, staff activation, and operator setup](access-control.md) and
[multi-carrier API, environment variables, sandbox setup, and fulfillment boundaries](shipping-integrations.md).

For isolated browser verification, run a separate seeded API/database and frontend, set the frontend `API_URL` to that API’s `/api/v1`, and set `E2E_BASE_URL` to the test frontend URL. Verify the ports are free first. Integration and browser runs share `artifacts/playwright`; run them sequentially to preserve traces. Commerce tests create products/orders and clear the demo shopper’s active cart, so use a disposable seeded database.

## October commerce audit fixes

Optional PostgreSQL race verification uses `codematics.postgres_test_settings` against a disposable database. Set `AUDIT_POSTGRES_PASSWORD` and, if needed, `AUDIT_POSTGRES_HOST`, `AUDIT_POSTGRES_PORT` (default 15432), `AUDIT_POSTGRES_USER` and `AUDIT_POSTGRES_DATABASE` (both default `proace_audit`). The configured test database is `test_proace_audit`; use a dedicated instance and a user allowed to create it.

```bash
.venv/bin/pytest server/payment/test_audit_regressions.py --ds=codematics.postgres_test_settings
```

The audit regressions include three concurrent-request tests that skip on SQLite. Run the mandatory offline suites normally, then run this optional suite to verify PostgreSQL row locking. Apply all Django migrations before testing the live app.

Live wallet-checkout browser tests require a funded seeded `shopper@proace.local` account. Successful checkout tests cancel their own orders afterward to restore inventory and wallet funds. On a slow development frontend, authentication, placement and preview assertions allow up to 30 seconds; per-test execution can be raised with Playwright `--timeout=120000`.
