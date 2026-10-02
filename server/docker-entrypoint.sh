#!/bin/sh
set -eu

if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
    python manage.py migrate --noinput
fi

python manage.py ensure_default_admin

if [ "${RUN_COLLECTSTATIC:-false}" = "true" ]; then
    python manage.py collectstatic --noinput
fi

mkdir -p "${PROMETHEUS_MULTIPROC_DIR:-/tmp/prometheus}"
exec "$@"
