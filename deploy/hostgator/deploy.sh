#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPOSITORY_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)
ENV_FILE=${HOSTGATOR_ENV_FILE:-$SCRIPT_DIR/.env}
NETWORK=${COMMERCE_NETWORK:-commerce-network}

if [ ! -f "$ENV_FILE" ]; then
    echo "Missing production environment file: $ENV_FILE" >&2
    exit 1
fi

chmod 600 "$ENV_FILE"
PUBLIC_DOMAIN=$(awk -F= '$1 == "PUBLIC_DOMAIN" {sub(/^[^=]*=/, ""); print; exit}' "$ENV_FILE")
PUBLIC_DOMAIN=${PUBLIC_DOMAIN:-proaceintlshoppingmall.com}
cd "$REPOSITORY_DIR"

docker network inspect "$NETWORK" >/dev/null 2>&1 || docker network create "$NETWORK" >/dev/null

docker compose --env-file "$ENV_FILE" -f server/compose.yaml build api notification-worker
docker compose --env-file "$ENV_FILE" -f client/compose.yaml build client

docker compose --env-file "$ENV_FILE" -f server/compose.yaml up -d --wait postgres redis elasticsearch
docker compose --env-file "$ENV_FILE" -f server/compose.yaml up -d api notification-worker
docker compose --env-file "$ENV_FILE" -f server/compose.yaml exec -T api python manage.py migrate --noinput
docker compose --env-file "$ENV_FILE" -f server/compose.yaml exec -T api python manage.py collectstatic --noinput
docker compose --env-file "$ENV_FILE" -f server/compose.yaml exec -T api python manage.py rebuild_product_index

docker compose --env-file "$ENV_FILE" -f client/compose.yaml up -d client
docker compose --env-file "$ENV_FILE" -f server/monitoring/compose.yaml up -d
docker compose --env-file "$ENV_FILE" -f deploy/hostgator/compose.yaml up -d

docker compose --env-file "$ENV_FILE" -f server/compose.yaml ps
docker compose --env-file "$ENV_FILE" -f client/compose.yaml ps
docker compose --env-file "$ENV_FILE" -f server/monitoring/compose.yaml ps
docker compose --env-file "$ENV_FILE" -f deploy/hostgator/compose.yaml ps

curl --fail --silent --show-error --retry 12 --retry-delay 5 \
    "https://$PUBLIC_DOMAIN/" >/dev/null
curl --fail --silent --show-error --retry 12 --retry-delay 5 \
    "https://$PUBLIC_DOMAIN/health/live/" >/dev/null

echo "HostGator deployment completed successfully."
