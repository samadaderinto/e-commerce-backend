# Server infrastructure

The backend has a local Compose stack and a Render-oriented CD path.

## Local services

- `api`: Django/Gunicorn.
- `postgres`: official PostgreSQL.
- `redis`: official Redis cache.
- `elasticsearch`: product search.
- monitoring stack: Prometheus, Grafana, Loki, Alloy, Tempo and exporters.

Run locally from `server/`:

```sh
../.venv/bin/python monitoring/init_local.py
docker compose -f compose.yaml up --build -d api redis postgres elasticsearch
docker compose -f monitoring/compose.yaml up -d
docker compose -f compose.yaml exec api python manage.py rebuild_product_index
```

## Render CD

GitHub Actions reads production secrets, syncs them to the Render service with
`.github/scripts/render-sync-env.py`, then triggers `RENDER_DEPLOY_HOOK_URL`.

Required Render control secrets:

- `RENDER_API_KEY`
- `RENDER_SERVICE_ID`
- `RENDER_DEPLOY_HOOK_URL`

Production app config should use GitHub Actions secrets, not committed env files.
