# Server ingress

See [Nginx security and deployment](nginx/README.md) for IP blocking, suspected-IP
limits, operator whitelisting, proxy trust, logging, and host/Kubernetes setup.

See [Monitoring and observability](monitoring/README.md) for health probes,
database/cache checks, Prometheus metrics, Grafana dashboards, traces, logs, and
local/production profiling.

The application container and official Redis cache are defined in
`server/compose.yaml`. Copy `.env.example` to `.env`, then run:

```sh
docker compose -f server/compose.yaml up --build -d api redis postgres
```

The API is available at `http://127.0.0.1:8000`; Redis and PostgreSQL are bound
to localhost only. The API container runs migrations on startup, stores
PostgreSQL data in the `postgres-data` volume, stores local uploads in
`media-data`, and uses `redis://redis:6379/0` inside Compose. Local Compose does
not depend on MinIO or any external object-storage registry.

For production, set `DJANGO_DEBUG=false`, replace every local default secret,
set a real `ALLOWED_HOSTS`, set `OBJECT_STORAGE_ENABLED=true` with credentials for
your S3-compatible provider, and set `RUN_MIGRATIONS=false` when more than one API
replica starts at once. Run migrations once as a release job, then start the API
replicas. For production, point `POSTGRES_HOST` at managed PostgreSQL and use a
secret-managed password rather than the local Compose defaults.

The local image does not install AWS SDK packages because local uploads use the
`media-data` volume. For an S3-compatible production deployment, set
`OBJECT_STORAGE_ENABLED=true` and `INSTALL_OBJECT_STORAGE=true` before building;
the matching AWS SDK pair is then installed from `requirements-storage.txt`.
