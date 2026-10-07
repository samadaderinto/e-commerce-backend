# E-commerce API

## Tech Stack

**Server:** Django, Django rest Framework, HTML, Docker, Kubernetes, Jekins

For the current containerized setup, use the repository-level instructions in
[`../README.md`](../README.md). The short version is:

```sh
cd server
../.venv/bin/python monitoring/init_local.py
docker compose -f compose.yaml up --build -d api redis postgres elasticsearch
docker compose -f monitoring/compose.yaml up -d
docker compose -f compose.yaml exec api python manage.py rebuild_product_index
```

This starts Django, the official Redis cache, official PostgreSQL database,
Elasticsearch, Prometheus, Grafana, Tempo, Loki, Alloy and the Elasticsearch
exporter. Alloy collects Docker container stdout into Loki, so the API, Redis,
Postgres, Elasticsearch and monitoring logs are searchable in Grafana Explore.
Local media uses the `media-data` volume. See
[`monitoring/README.md`](monitoring/README.md) for health checks, dashboards,
profiling, logs, and production settings.

## Run Locally

Clone the project

```bash
  git clone https://github.com/samadaderinto/e-commerce-backend
```

Go to the project directory

```bash
  cd codematics
```

Install dependencies

```bash
  pip3 install -r requirements.txt
```
or 

```bash
  pip install -r requirements.txt
```

Create and Update migrations

```bash
  python3 manage.py makemigrations; python3 manage.py migrate
```

or 

```bash
  python manage.py makemigrations; python manage.py migrate
```

Start the server

```bash
  python3 manage.py runserver 
```

or 

```bash
  python manage.py runserver 
```

## Populate Fake Data (Local / Dev)

Seed a large volume of realistic e-commerce data (users, stores, catalog products with variants & specs, orders with USPS/FedEx tracking, seller tiers, financial ledgers, reviews, coupons, wallets, and notifications):

```bash
# Standard seed (~150 products, 350 orders, 65 users, 12 stores)
python manage.py populate_fake_data

# Large volume seed (~500 products, 1500 orders, 200 users, 25 stores)
python manage.py populate_fake_data --scale large --clear

# Custom volume
python manage.py populate_fake_data --products 1000 --orders 3000 --users 300

# Alias also supported
python manage.py seed_fake_data
```

Default development accounts created (all share password `Password123!` or custom `--password`):
- **Super Admin**: `admin@proace.local` (Full superuser and staff permissions)
- **Staff**: `staff@proace.local` (Staff portal & blog author)
- **Vendor / Merchant**: `merchant@proace.local` (Owns flagship ProAce Select & Aura Audio, active payouts & ledgers)
- **Seller**: `seller@proace.local` (Owns Apex Athletics & affiliate links)
- **Shopper**: `shopper@proace.local` (Customer with active cart, addresses, order history, wishlist, and wallet balance)
- **Buyer**: `buyer@proace.local` (Customer account)

## Project Structure

```
codematics
├── templates
│   └── email-templates
│      └── (html files)
│
└── media
│    └── images
│       └── (image files)
│
└── codematics
│    ├── (default files/ folders) e.g __pycache__, migrations.
│    ├── asgi.py
│    ├── settings.py
│    ├── urls.py 
│    ├── wsgi.py
│    └── __init__.py
│
└── affiliates
│    ├── (default files/ folders) e.g __pycache__, migrations.
│    ├── admin.py
│    ├── apps.py
│    ├── serializers.py   
│    ├── models.py
│    ├── urls.py
│    ├── views.py
│    └── test.py
│    
└──  cart
│    ├── (default files/ folders) e.g __pycache__, migrations.
│    ├── admin.py
│    ├── apps.py
│    ├── serializers.py   
│    ├── models.py
│    ├── urls.py
│    ├── views.py
│    └── test.py
│
└── core
│    ├── (default files/ folders) e.g __pycache__, migrations.
│    ├── admin.py
│    ├── apps.py
│    ├── serializers.py   
│    ├── models.py
│    ├── urls.py
│    ├── views.py
│    └── test.py
│
└──  payment
│    ├── (default files/ folders) e.g __pycache__, migrations.
│    ├── admin.py
│    ├── apps.py
│    ├── serializers.py   
│    ├── models.py
│    ├── urls.py
│    ├── views.py
│    └── test.py'
│
└──  product
│    ├── (default files/ folders) e.g __pycache__, migrations.
│    ├── admin.py
│    ├── apps.py
│    ├── serializers.py   
│    ├── models.py
│    ├── urls.py
│    ├── views.py
│    └── test.py
│
└──  staff
│    ├── (default files/ folders) e.g __pycache__, migrations.
│    ├── admin.py
│    ├── apps.py
│    ├── serializers.py   
│    ├── models.py
│    ├── urls.py
│    ├── views.py
│    └── test.py
│
└──  store
│    ├── (default files/ folders) e.g __pycache__, migrations.
│    ├── admin.py
│    ├── apps.py
│    ├── serializers.py   
│    ├── models.py
│    ├── urls.py
│    ├── views.py
│    └── test.py
│
└──  event_notification
│    ├── (default files/ folders) e.g __pycache__, migrations.
│    ├── admin.py
│    ├── apps.py
│    ├── serializers.py   
│    ├── models.py
│    ├── urls.py
│    ├── views.py
│    └── test.py
│
└── DockerFile
└── .dockerignore
└── deployment.md
└── entrypoint.sh
└── jenkinsfile
└── manage.py
└── pytest.ini
└── requirements.txt
```

## Project Structure details
1. migrations:
In Django, migrations are a way to manage changes to your models (database schema) over time. When you make changes to your models, such as adding a new field or changing an 
existing one, Django can automatically generate migration files that represent these changes.

2. settings.py:
In Django, this is a crucial file that holds various configuration settings for your django web application like database settings, middlewares, etc.

3. requirements.txt:
In Django, this file is often used to list all the Python packages that are required for the project to run. This file can be used with tools like pip to install all dependencies at once. 

4. urls.py
In Django, this files are used to define URL patterns for directing incoming web requests to the appropriate view functions

### Stable demo scenarios

All three entry points (`seed_demo`, `populate_fake_data`, and `seed_fake_data`)
include the same scenario coverage. `seed_demo` requires a password of at least
12 characters; the other commands default to `Password123!` in development.
Existing named demo accounts receive the supplied password again on each run.

- `shopper@proace.local` and `buyer@proace.local`: shoppers without stores.
- `seller@proace.local`: one store (Apex Athletics).
- `merchant@proace.local`: multiple stores, including all six seller badge tiers.
- `pending-seller@proace.local`: pending and active-but-unverified stores.
- `blocked-seller@proace.local`: a blocked store with a moderation reason.
- `admin@proace.local` and `staff@proace.local`: active administration accounts.
- `blocked-staff@proace.local` and `unverified@proace.local`: inactive accounts;
  login is intentionally denied.

Stable stores use `demo-` usernames: `starter`, `booster`, `accelerator`, `power`,
`mega`, `legendary`, `pending`, `unverified`, `blocked`, and `empty`.
Badge stores include historical earnings records at each tier threshold.
Products include bestseller/new/sold-out labels, low stock, discounts, and hidden
listings. The random catalog additionally includes variants, digital products,
flash sales, reviews, orders, wallets, refunds, coupons, and affiliates.
When Elasticsearch is enabled, seeding rebuilds the product search index after
bulk creation. Scale presets control the random volume; fixed scenarios are added on every run.
The scenario fixtures are updated in place; the volume generator adds products
and orders on repeated runs. Use `--clear` only when you intend to delete existing
commerce data in development.

If every local page keeps loading, check `docker ps`: paused containers retain
published ports but cannot answer requests. Unpause the commerce frontend,
backend, Postgres, Redis, and Elasticsearch together. The frontend uses `API_URL`
(`http://api:8000/api/v1` in Compose, `http://127.0.0.1:8000/api/v1` locally).

## Back-office roles and shipping

See the [endpoint permission matrix and staff onboarding](../docs/access-control.md)
and [carrier setup and checkout API](../docs/shipping-integrations.md).
Apply the new core, store, and payment migrations before starting this version.
Staff/admin accounts use operational workspaces and cannot shop. Grafana requires
technical-admin credentials; anonymous access is disabled.

See [UI components and live event pipeline](../docs/ui-and-events.md) for responsive conventions, pagination, carrier selection, cart states, scoped SSE events, and verification procedures.

## Running Tests

Execute the automated backend test suite using the isolated SQLite test settings:

```bash
DJANGO_SETTINGS_MODULE=codematics.test_settings ./.venv/bin/pytest server/
```

- **Database**: SQLite in-memory/file (`codematics.test_settings`), preventing contamination of development databases.
- **Carriers**: `SHIPPING_RATE_MODE = 'demo'` ensures external shipping APIs (DHL/USPS/FedEx) are isolated during tests.
- **Asynchronous tasks**: Celery is configured in eager execution mode (`CELERY_TASK_ALWAYS_EAGER = True`).
