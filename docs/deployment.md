# HostGator VPS deployment

Production runs on a HostGator VPS or dedicated server with root/SSH access.
Shared hosting is not supported because the application requires Docker,
long-running worker processes, PostgreSQL, Redis, Elasticsearch, and the
observability services.

Set `CELERY_WORKER_CONCURRENCY` explicitly in the production environment after
capacity testing. The deployment helper reuses `server/compose.yaml`, whose
default pool is 2 for the measured local memory profile; it is not a production
throughput guarantee. See [worker memory tuning](performance.md#local-celery-worker-memory)
for measurements and the seven-process rollback example.

The production topology is:

- Caddy on ports 80/443, with automatic TLS for
  `proaceintlshoppingmall.com` and its `www` name.
- Next.js as the public storefront and same-origin `/api/*` gateway.
- Django API and Celery notification worker on the private Docker network.
- PostgreSQL, Redis, and Elasticsearch with persistent Docker volumes and
  loopback-only host bindings.
- Prometheus, Grafana, Loki, Tempo, Alloy, and exporters. Grafana and
  Prometheus are loopback-only rather than public.

## Initial VPS preparation

Use a current Linux VPS with at least 4 vCPU, 8 GB RAM, and sufficient SSD
storage. Elasticsearch and the monitoring stack are memory-intensive; 16 GB RAM
is preferable for production traffic. In HostGator DNS, point both the apex `A`
record and `www` record at the VPS public IP. Open inbound TCP 22, 80, and 443,
and UDP 443. Do not expose 3000, 3002, 5432, 6379, 8000, 9090, or 9200.

If the server was provisioned with cPanel/Apache or another web server already
using ports 80 and 443, either stop that listener or configure it as the TLS
proxy instead of Caddy. Do not start this Caddy stack until those ports are free.

Install Docker Engine, the Docker Compose plugin, `rsync`, and `curl`. Add the
deployment user to the Docker group, create a dedicated SSH key, and confirm:

```sh
docker version
docker compose version
```

## Production environment

Copy `deploy/hostgator/.env.example` to a local file outside Git, replace every
placeholder, and retain it securely. `POSTGRES_PASSWORD` and
`POSTGRES_EXPORTER_PASSWORD` must match. The file is deployed to
`deploy/hostgator/.env` with mode 0600 and is ignored by Git.

Before enabling production email, set a Resend API key and a sender whose domain
has been verified. For durable uploaded media across hosts, enable the existing
S3-compatible storage settings; a single-server deployment can use the Docker
media volume but must include it in an off-server backup policy.

### Production Environment Variables Reference

The `.env` file deployed to `deploy/hostgator/.env` must contain the following production variables (derived from `deploy/hostgator/.env.example`):

| Variable | Description | Example / Recommended Value |
| :--- | :--- | :--- |
| `PUBLIC_DOMAIN` | Production apex domain | `proaceintlshoppingmall.com` |
| `COMMERCE_NETWORK` | Shared Docker network name | `commerce-network` |
| `DJANGO_DEBUG` | Set strictly to `false` in production | `false` |
| `SECRET_KEY` | 50+ character random Django secret | `openssl rand -base64 48` |
| `ALLOWED_HOSTS` | Whitelisted host headers | `proaceintlshoppingmall.com,www.proaceintlshoppingmall.com,api,client` |
| `FRONTEND_URL` | Deployed frontend origin | `https://proaceintlshoppingmall.com` |
| `CSRF_TRUSTED_ORIGINS` | Trusted origins for CSRF | `https://proaceintlshoppingmall.com,https://www.proaceintlshoppingmall.com` |
| `SECURE_SSL_REDIRECT` | Enforce HTTPS redirects | `true` |
| `SECURE_HSTS_SECONDS` | HTTP Strict Transport Security duration | `31536000` |
| `API_URL` | Docker internal API proxy address | `http://api:8000/api/v1` |
| `DEFAULT_ADMIN_EMAIL` | Superuser login email | `admin@proaceintl.com` |
| `DEFAULT_ADMIN_PASSWORD`| Initial superuser password | Strong 16+ char password |
| `TECHNICAL_ADMIN_EMAIL` | Technical super admin (synced with MinIO/Grafana) | `${DEFAULT_ADMIN_EMAIL}` |
| `TECHNICAL_ADMIN_PASSWORD` | Technical admin password | `${DEFAULT_ADMIN_PASSWORD}` |
| `DEFAULT_ADMIN_FIRST_NAME` | Superuser first name | `ProAce` |
| `DEFAULT_ADMIN_LAST_NAME` | Superuser last name | `Administrator` |
| `DEFAULT_ADMIN_GENDER` | Gender status (`male` or `female`) | `male` |
| `DEFAULT_ADMIN_PHONE` | E.164 formatted telephone | `+13013251550` |
| `POSTGRES_DB` | PostgreSQL database name | `commerce` |
| `POSTGRES_USER` | PostgreSQL user | `commerce` |
| `POSTGRES_PASSWORD` | Strong database password | `openssl rand -hex 24` |
| `POSTGRES_EXPORTER_USER` | Exporter user | `${POSTGRES_USER}` |
| `POSTGRES_EXPORTER_PASSWORD` | Exporter password | `${POSTGRES_PASSWORD}` |
| `OBSERVABILITY_TOKEN` | Private bearer token for `/metrics/` | `openssl rand -hex 32` |
| `STRIPE_SECRET` | Stripe Secret API Key (live or test) | `sk_live_...` |
| `PUBLISHER_KEY` | Stripe Publishable API Key | `pk_live_...` |
| `STRIPE_WALLET_PAYMENT_METHODS` | Payment methods for wallet top-up | `cashapp` |
| `STRIPE_CURRENCY` | Base transaction currency | `usd` |
| `RESEND_API_KEY` | Resend API key for transactional emails | `re_...` |
| `RESEND_FROM_EMAIL` | Verified sender address | `ProAce <admin@proaceintl.com>` |
| `ELASTICSEARCH_ENABLED` | Enable product fuzzy search engine | `true` |
| `ELASTICSEARCH_JAVA_OPTS` | JVM heap limit for VPS RAM | `-Xms512m -Xmx512m` |
| `SHIPPING_RATE_MODE` | Live shipping rate calculation | `live` |
| `SHIPPING_SANDBOX` | Toggle carrier test/sandbox mode | `false` |
| `USPS_CLIENT_ID` / `_SECRET` | USPS carrier credentials | OAuth2 credentials |
| `FEDEX_API_KEY` / `_SECRET_KEY` | FedEx carrier credentials | REST API credentials |
| `DHL_API_KEY` / `_SECRET` | DHL Express credentials | API keys |
| `UPS_CLIENT_ID` / `_SECRET` | UPS carrier credentials | OAuth2 credentials |

## GitHub Actions Production Secrets & Configuration

In your GitHub repository, navigate to **Settings** → **Environments** → create an environment named **`production`**.

### 1. HostGator VPS Connection Secrets (Required)
| Secret | Purpose | How to obtain / configure |
| :--- | :--- | :--- |
| `HOSTGATOR_HOST` | HostGator VPS IP address or hostname | e.g. `198.54.xxx.xxx` or `vps.proaceintlshoppingmall.com` |
| `HOSTGATOR_PORT` | SSH Port | `22` (or your custom SSH port) |
| `HOSTGATOR_USER` | Deployment user on the VPS | e.g. `deploy` or `root` |
| `HOSTGATOR_DEPLOY_PATH` | Target directory on the VPS | `/opt/proace-commerce` |
| `HOSTGATOR_SSH_PRIVATE_KEY` | Private SSH key for passwordless login | The content of `~/.ssh/id_ed25519` (deploy user) |
| `HOSTGATOR_SSH_KNOWN_HOSTS` | VPS SSH host fingerprint | Run `ssh-keyscan -p 22 <HOST>` from your local machine |

### 2. Application Secrets & Credentials (Granular & Auditable)
Add each sensitive secret directly into the `production` environment:
| Secret | Purpose | Example / Notes |
| :--- | :--- | :--- |
| `PROD_SECRET_KEY` | Django application secret | `openssl rand -base64 48` |
| `PROD_POSTGRES_PASSWORD` | PostgreSQL database password | Strong random password |
| `PROD_ADMIN_PASSWORD` | Default superuser password | Strong 16+ char password |
| `PROD_TECHNICAL_ADMIN_PASSWORD` | Technical Super Admin password (synced with Grafana & MinIO) | Defaults to `PROD_ADMIN_PASSWORD` if omitted |
| `PROD_OBSERVABILITY_TOKEN` | Bearer token for `/metrics/` scrape | `openssl rand -hex 32` |
| `STRIPE_SECRET` | Stripe Secret API Key | `sk_live_...` |
| `PUBLISHER_KEY` | Stripe Publishable API Key | `pk_live_...` |
| `RESEND_API_KEY` | Resend API key for transactional emails | `re_...` |
| `USPS_CLIENT_ID` / `_SECRET` | USPS API credentials (optional) | Live or sandbox OAuth |
| `FEDEX_API_KEY` / `_SECRET_KEY` | FedEx API credentials (optional) | REST API credentials |
| `DHL_API_KEY` / `_SECRET` | DHL Express credentials (optional) | API keys |
| `UPS_CLIENT_ID` / `_SECRET` | UPS API credentials (optional) | OAuth2 credentials |

### 3. Optional Environment Variables (GitHub Environment Variables)
Under **Environment Variables** in the `production` environment (or defaults will be used):
- `PUBLIC_DOMAIN`: defaults to `proaceintlshoppingmall.com`
- `PROD_ADMIN_EMAIL`: defaults to `admin@proaceintl.com`
- `RESEND_FROM_EMAIL`: defaults to `ProAce <admin@proaceintl.com>`
- `SHIPPING_RATE_MODE`: `live` (or `demo`)
- `SHIPPING_SANDBOX`: `false` (or `true`)

Obtain the verified host-key entry from a trusted machine or the HostGator
console. Do not populate it from an unauthenticated `ssh-keyscan` during CI.

On a push to `main` or `master`, CI runs backend, frontend, security, and CodeQL
checks. It then uploads the repository and environment, builds the images on the
VPS, starts dependencies, runs migrations/static collection/search indexing,
starts all application and monitoring containers, and verifies the public home
and live-health endpoints over HTTPS.

## Manual deployment

After uploading the repository and production environment to the VPS:

```sh
cd /opt/proace-commerce
chmod +x deploy/hostgator/deploy.sh deploy/hostgator/backup.sh
deploy/hostgator/deploy.sh
```

The deployment script is safe to rerun. Docker named volumes retain database,
search, uploads, Caddy certificates, and monitoring data.

## Monitoring access

Prometheus continues to scrape the API, PostgreSQL, Redis, Elasticsearch,
Docker, the VPS host, Grafana, Loki, and Tempo every 15 seconds. Access Grafana
without exposing it publicly by creating an SSH tunnel:

```sh
ssh -L 3002:127.0.0.1:3002 HOSTGATOR_USER@HOSTGATOR_HOST
```

Then open `http://127.0.0.1:3002`. Use the configured default admin email and
password. Prometheus can be reached similarly with local port 9090.

## Backups

Run a daily PostgreSQL backup and copy the result to storage outside the VPS.
For example, install a root crontab entry:

```cron
17 2 * * * HOSTGATOR_BACKUP_DIR=/var/backups/proace-commerce /opt/proace-commerce/deploy/hostgator/backup.sh >> /var/log/proace-backup.log 2>&1
```

The script retains 14 days by default. Database-only backups do not protect
Docker media, Elasticsearch, Grafana, or Caddy volumes. Add encrypted off-server
volume backups and test restoration before launch.

## Operational checks

```sh
cd /opt/proace-commerce
docker compose --env-file deploy/hostgator/.env -f server/compose.yaml ps
docker compose --env-file deploy/hostgator/.env -f client/compose.yaml ps
docker compose --env-file deploy/hostgator/.env -f monitoring/compose.yaml ps
docker compose --env-file deploy/hostgator/.env -f deploy/hostgator/compose.yaml ps
curl --fail https://proaceintlshoppingmall.com/health/live/
```

If a deployment fails, inspect `docker compose ... logs`, fix the configuration,
and rerun the deployment script. Never delete Docker volumes as a rollback.

## Back-office roles and shipping

See the [endpoint permission matrix and staff onboarding](access-control.md)
and [carrier setup and checkout API](shipping-integrations.md).
Apply the new core, store, and payment migrations before starting this version.
Staff/admin accounts use operational workspaces and cannot shop. Grafana requires
technical-admin credentials; anonymous access is disabled.

Email backend selection: use `EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend` for normal local development; use `EMAIL_BACKEND=notification.email_backend.ResendEmailBackend` for production or temporary local delivery testing. An explicit console backend overrides a configured Resend key. See [local and production email setup](getting-started.md#email-backend-local-development-and-resend-testing) for verified sender requirements, recreating services after environment changes, and returning to console mode.

## Transitioning notifications from local to production

1. Keep normal local development explicitly on console mail in `server/.env`.
   For a temporary local Resend test, use the Resend backend, an actual API key,
   and a verified sender; recreate API, worker and scheduler together. Restore
   console mode afterward. See [worker settings](getting-started.md#notification-worker-settings-and-troubleshooting).
2. Verify the intended sender domain in Resend before enabling production sends.
   Set `EMAIL_BACKEND=notification.email_backend.ResendEmailBackend`,
   `RESEND_API_KEY` and `RESEND_FROM_EMAIL` in the protected production environment.
   Set `DJANGO_DEBUG=false` and `FRONTEND_URL` to the public HTTPS storefront so
   email links point to production. Use production credentials and a production
   database/broker; do not deploy the local demo database or run demo seeding.
3. Account for the current Compose environment wiring: `--env-file
   deploy/hostgator/.env` supplies Compose interpolation, while the backend services
   also load `server/.env` as their container `env_file`. `EMAIL_BACKEND` and
   `RESEND_FROM_EMAIL` currently come from that container env file, not explicit
   Compose environment mappings. Ensure the **production host's `server/.env`**
   contains the intended production backend and sender as well; a local console
   setting there will override automatic Resend selection. Keep both files private,
   untracked and permission-restricted. Do not copy a developer's local environment
   unchanged to the production host. Declare shared values once in the production
   environment and reference them through variable substitution where appropriate.
4. Follow the deployment procedure above, apply migrations through the API, and
   explicitly start/recreate the notification worker and scheduler. The current
   `deploy.sh` starts API and worker but does not start `celery-beat`; run the
   following additional command on the production host from the repository root:

   ```sh
   docker compose --env-file deploy/hostgator/.env -f server/compose.yaml up -d --no-deps --force-recreate api notification-worker celery-beat notification-stream
   ```

   This refreshes environment settings without removing infrastructure or volumes.
   Environment-only changes do not require an image rebuild. For application code
   updates, rebuild the affected services before recreation. Run one scheduler for
   this broker/environment to avoid duplicate periodic dispatch.
5. Verify the effective email backend in both API and worker using the commands
   in the worker guide, adding `--env-file deploy/hostgator/.env` after `docker compose`.
   Check container status, worker readiness and scheduler recovery logs. Send a
   controlled email through a normal application flow to a recipient you control;
   check outbox status, Resend delivery events, links and the actual inbox. Do not
   interpret a historical console `sent` record as live delivery. Retry historical
   failed/console-completed messages only deliberately after configuration is fixed.
6. Keep `FCM_ENABLED=false` if email is the only channel being enabled. To enable
   browser push, configure `FIREBASE_PROJECT_ID`, backend Firebase credentials and
   the existing frontend Firebase configuration, rebuild the client when its build
   configuration changes, then test recipient permissions and device registration.
   Email credentials alone do not enable push.

If email must be temporarily disabled in production, switching to console stops
real sends but records them as handled; preserve the affected delivery IDs for a
controlled recovery. Console logs may contain message content, so restrict log
access. Correct the configuration and recreate services before resuming live mail.

The production `.env.example` contains fictional format samples, including an intentionally invalid Firebase private key. Replace every sample credential and account detail before deploying, use live Stripe keys, verify the email sender, and clear optional integrations that are not enabled. See [the example environment guide](getting-started.md#reading-the-example-environment-files).
## Dedicated notification streaming

The stream image sets the Docker build argument `INSTALL_STREAM_POOL=true` to install `requirements-stream.txt`. Each stream worker uses a PostgreSQL pool capped at four physical sockets (`min_size=0`, acquisition timeout 3 seconds), returning connections after access checks instead of retaining one per SSE thread or reconnecting on every heartbeat. Install that requirements file explicitly when deploying the dedicated settings without Compose.

The backend Compose stack now includes internal `notification-stream`; deploy it with `api`, `notification-worker` and `celery-beat` before recreating `client`. The HostGator helper builds/starts all four backend consumers. Browser traffic remains same-origin: only `/api/notifications/stream` is routed by Next.js to the internal stream process. `CONTAINER_NOTIFICATION_STREAM_URL` defaults to `http://notification-stream:8000/api/v1`; token refresh stays on the main API. The new service exposes only the stream and health routes, publishes no host port, uses normal JWT/access checks, runs no migrations, and isolates metrics files. Defaults are one process / 32 threads (`STREAM_WORKERS`, `STREAM_THREADS`); budget database connections across services. See [performance](performance.md) for limitations, verification and routing rollback. Migration `product.0015_catalog_pagination_indexes` must be applied through the API container; on a large production table, schedule index creation or use a reviewed concurrent-index rollout to avoid write-lock surprises.
