# HostGator VPS deployment

Production runs on a HostGator VPS or dedicated server with root/SSH access.
Shared hosting is not supported because the application requires Docker,
long-running worker processes, PostgreSQL, Redis, Elasticsearch, and the
observability services.

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

Encode the completed environment file for GitHub Actions:

```sh
base64 < hostgator-production.env | tr -d '\n'
```

## GitHub production secrets

Configure these secrets in the repository's `production` environment:

| Secret | Purpose |
| --- | --- |
| `HOSTGATOR_HOST` | VPS hostname or IP address |
| `HOSTGATOR_PORT` | SSH port; defaults to `22` |
| `HOSTGATOR_USER` | Non-root deployment user with Docker access |
| `HOSTGATOR_DEPLOY_PATH` | Absolute remote path, such as `/opt/proace-commerce` |
| `HOSTGATOR_SSH_PRIVATE_KEY` | Private deployment key |
| `HOSTGATOR_SSH_KNOWN_HOSTS` | Verified `known_hosts` entry for the VPS |
| `HOSTGATOR_ENV_B64` | Base64-encoded production environment file |

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
docker compose --env-file deploy/hostgator/.env -f server/monitoring/compose.yaml ps
docker compose --env-file deploy/hostgator/.env -f deploy/hostgator/compose.yaml ps
curl --fail https://proaceintlshoppingmall.com/health/live/
```

If a deployment fails, inspect `docker compose ... logs`, fix the configuration,
and rerun the deployment script. Never delete Docker volumes as a rollback.
