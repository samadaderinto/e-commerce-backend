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
.venv/bin/python server/manage.py seed_demo --password 'ProaceDemo2026!'
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

The demo password above is for local seeded accounts only. `seed_demo` is
refused when `DJANGO_DEBUG=false`; do not use demo credentials or template
secrets in deployed environments. Local verification and password-reset
messages are printed by Django's console email backend.

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
workflow reads deployment values from Actions secrets and synchronizes backend
values to Render. Follow [server/deployment.md](../server/deployment.md) for the
required secret names and deployment procedure. Never commit real credentials.

## Check your setup

These root npm scripts delegate to the client workspace:

```sh
npm run typecheck
npm run test:unit
npm run build
```

Backend test settings are isolated from the local development database:

```sh
.venv/bin/python server/manage.py check --settings=codematics.test_settings
.venv/bin/python server/manage.py test storefront --settings=codematics.storefront_settings --noinput
```

The CI-equivalent pytest and coverage run uses the development dependencies in
[`server/Pipfile`](../server/Pipfile). To reproduce it, install Pipenv and run
these commands from `server/`:

```sh
pipenv install --dev --skip-lock
pipenv run python manage.py check --settings=codematics.test_settings
pipenv run coverage run -m pytest --verbose
pipenv run coverage report --show-missing
pipenv run python manage.py test storefront --settings=codematics.storefront_settings --noinput
```

The integration and browser tests require the API and frontend to be running,
and seeded demo accounts to exist:

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
