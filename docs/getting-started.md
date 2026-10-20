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
secrets in deployed environments. A seed run is atomic, requires at least 11
users for its guaranteed accounts, and never prints the password. If a step
fails, its generated rows and a requested `--clear` are rolled back together.
The catalog search index is rebuilt after the database transaction commits.

### Seeding & Demo Data
- **Authoritative Seeding (`populate_fake_data`)**: The single command to populate the local environment. It always creates all essential role profiles (`admin@proace.local`, `business-admin@proace.local`, `staff@proace.local`, `seller@proace.local`, `shopper@proace.local`) along with a full catalog, reviews, orders, and financial escrow balances.
  ```sh
  .venv/bin/python server/manage.py populate_fake_data
  ```
- **Reindexing Search (`rebuild_product_index`)**: Rebuilds the Elasticsearch catalog index (`commerce-products`).
  See [development seeding](backend.md#development-seeding) for presets, overrides, and safety rules.

### Email backend: local development and Resend testing

Keep normal local development on the console backend in `server/.env`:

```dotenv
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
```

To test real Resend delivery locally, temporarily replace that value with:

```dotenv
EMAIL_BACKEND=notification.email_backend.ResendEmailBackend
```

Set `RESEND_API_KEY` to your actual key and `RESEND_FROM_EMAIL` to a sender on
your Resend-verified domain. Keep secrets out of Git. This setting sends real
emails even when Django runs locally. Trigger a normal email flow with a test
recipient you control, then check both Resend delivery status and the recipient's
inbox; rendering a template or creating an outbox row alone does not verify delivery.

After changing `server/.env`, recreate the affected Compose services from the
repository root so their environment is refreshed (a plain restart is insufficient):

```sh
docker compose -f server/compose.yaml up -d --no-deps --force-recreate api notification-worker celery-beat notification-stream
```

For processes running directly on your host, stop and restart the API, worker and
scheduler instead. Switch `EMAIL_BACKEND` back to the console value after the local
test and recreate/restart those processes again. Console email output appears in
the process handling delivery, normally the notification worker for queued email.
Staff credential issuance requires a private backend and cannot use console mail.

Production should explicitly use `notification.email_backend.ResendEmailBackend`
with its own API key and verified sender. If `EMAIL_BACKEND` is omitted, the app
selects Resend when `RESEND_API_KEY` is present or debug mode is off; otherwise it
uses console mail. An explicit console setting overrides that automatic selection,
even when a real key is configured. Tests use an in-memory backend and do not send
email.

### Notification worker settings and troubleshooting

The API creates inbox/outbox records; `notification-worker` sends queued email and
push. `celery-beat` schedules recovery of pending or abandoned deliveries. All three
must use the intended environment. Updating the API alone can leave the worker on
console mail, even though the API reports Resend.

| Setting | Local default / purpose | Production requirement |
| --- | --- | --- |
| `EMAIL_BACKEND` | Explicit console backend for ordinary development | `notification.email_backend.ResendEmailBackend` |
| `RESEND_API_KEY` | Required only for a real email test | Actual production Resend key |
| `RESEND_FROM_EMAIL` | Actual sender for real email tests | Address on a Resend-verified domain |
| `FRONTEND_URL` | `http://127.0.0.1:3000` | Public HTTPS storefront origin |
| `CELERY_BROKER_URL` | Compose sets `redis://redis:6379/1` | API, worker and scheduler share the same broker |
| `CELERY_WORKER_CONCURRENCY` | Local Compose defaults to `2` | Prefork children for `notification-worker` only; use `7` for the previous pool size |
| `NOTIFICATION_DELIVERY_MAX_ATTEMPTS` | `8` | Bounded retries; adjust only deliberately |
| `NOTIFICATION_DELIVERY_STALE_SECONDS` | `300` | Recovery threshold for abandoned work |
| `FCM_ENABLED` | `false` | Enable only after Firebase credentials/configuration are ready |

Check the effective backend in both running containers without printing API keys:

```sh
docker compose -f server/compose.yaml exec -T api python manage.py shell -c 'from django.conf import settings; print(settings.EMAIL_BACKEND)'
docker compose -f server/compose.yaml exec -T notification-worker python manage.py shell -c 'from django.conf import settings; print(settings.EMAIL_BACKEND)'
docker compose -f server/compose.yaml ps api notification-worker celery-beat notification-stream
```

A valid Resend key does not verify the sender domain. If Resend rejects the sender,
complete domain verification in the Resend dashboard or select a sender on an
already verified domain. Apply any changed environment to all three services.
Pending deliveries retry until the configured limit; failed deliveries need a
controlled retry after the cause is corrected. Messages marked `sent` through
console mail do not resend automatically when switching to Resend. Resend acceptance
also does not establish inbox delivery: check provider delivery events and the inbox.
Avoid repeatedly toggling store status just to trigger another email.

See [transitioning notifications to production](deployment.md#transitioning-notifications-from-local-to-production)
for deployment environment handling and release checks.

## Run with containers

The backend Compose stack provides PostgreSQL, Redis and Elasticsearch; the
monitoring Compose stack is optional. The frontend can also run directly on
Node.js while the backend stack runs in containers.

Follow the root [container walkthrough](../README.md#run-locally)
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

Backend test settings are isolated from the local development database. Run the
complete offline pytest suite directly with your virtual environment:

```sh
# Offline backend pytest suite
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

## PostgreSQL concurrency tests

Optional PostgreSQL race verification uses `codematics.postgres_test_settings` against a disposable database. Set `AUDIT_POSTGRES_PASSWORD` and, if needed, `AUDIT_POSTGRES_HOST`, `AUDIT_POSTGRES_PORT` (default 15432), `AUDIT_POSTGRES_USER` and `AUDIT_POSTGRES_DATABASE` (both default `proace_audit`). The configured test database is `test_proace_audit`; use a dedicated instance and a user allowed to create it.

```bash
.venv/bin/pytest server/payment/test_audit_regressions.py --ds=codematics.postgres_test_settings
```

These tests include concurrent-request cases that skip on SQLite. Run the
mandatory offline suites first, then use PostgreSQL to verify row locking.
Apply all Django migrations before testing the live app. The backend guide also
describes the [isolated Compose test database](backend.md#verification-and-operation).

Live wallet-checkout browser tests require a funded seeded `shopper@proace.local` account. Successful checkout tests cancel their own orders afterward to restore inventory and wallet funds. On a slow development frontend, authentication, placement and preview assertions allow up to 30 seconds; per-test execution can be raised with Playwright `--timeout=120000`.

### Reading the example environment files

`client/.env.example`, `server/.env.example` and `deploy/hostgator/.env.example`
contain fictional values to show each setting's expected shape. They are format
references, not working credentials. Replace all `FAKE`/`REPLACE` values before
using a provider; clear unused provider keys and social IDs for offline development
so their presence does not make unavailable integrations appear configured. Keep
local email on console and `FCM_ENABLED=false` until real credentials are ready.

Firebase browser values come from the web app configuration; the VAPID value is
the public Web Push certificate key. Backend `FIREBASE_CREDENTIALS_JSON` requires
the entire downloaded service-account JSON on one quoted line, preserving `\n`
inside the private key. The example private key is intentionally invalid. Google
web OAuth client IDs end in `.apps.googleusercontent.com` and must match in both
applications; Apple uses the configured Services ID. Carrier and payment samples
must be replaced with credentials issued by those providers. Never copy test Stripe
keys to production: use the production account's live keys there. Use your actual
verified Resend sender and unique production secrets, not example account details.
