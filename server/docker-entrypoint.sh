#!/bin/sh
set -eu

unset prometheus_multiproc_dir
if [ -n "${PROMETHEUS_MULTIPROC_DIR:-}" ]; then
    PROMETHEUS_MULTIPROC_DIR=$(mktemp -d /tmp/proace-metrics.XXXXXX)
    export PROMETHEUS_MULTIPROC_DIR
else
    unset PROMETHEUS_MULTIPROC_DIR
fi

if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
    python manage.py migrate --noinput
    python manage.py ensure_default_admin
fi

if [ "${RUN_COLLECTSTATIC:-false}" = "true" ]; then
    python manage.py collectstatic --noinput
fi

exec "$@"
