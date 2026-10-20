#!/bin/bash
set -euo pipefail
umask 077

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPOSITORY_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)
ENV_FILE=${HOSTGATOR_ENV_FILE:-$SCRIPT_DIR/.env}
BACKUP_DIR=${HOSTGATOR_BACKUP_DIR:-/var/backups/proace-commerce}
RETENTION_DAYS=${HOSTGATOR_BACKUP_RETENTION_DAYS:-14}
STAMP=$(date -u +%Y%m%dT%H%M%SZ)

mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"
cd "$REPOSITORY_DIR"

TEMP_ARCHIVE=$(mktemp "$BACKUP_DIR/.postgres-$STAMP.XXXXXXXX.sql.gz")
cleanup() {
    if [ -n "$TEMP_ARCHIVE" ]; then
        rm -f -- "$TEMP_ARCHIVE"
    fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

docker compose --env-file "$ENV_FILE" -f server/compose.yaml exec -T postgres \
    sh -c 'pg_dump --clean --if-exists --no-owner --username "$POSTGRES_USER" "$POSTGRES_DB"' \
    | gzip -9 > "$TEMP_ARCHIVE"

gzip -t "$TEMP_ARCHIVE"
if ! gzip -dc "$TEMP_ARCHIVE" | awk 'END {exit NR == 0}'; then
    echo "Database backup is empty or invalid." >&2
    exit 1
fi
mv -- "$TEMP_ARCHIVE" "$BACKUP_DIR/postgres-$STAMP.sql.gz"
TEMP_ARCHIVE=''

find "$BACKUP_DIR" -type f -name 'postgres-*.sql.gz' -mtime "+$RETENTION_DAYS" -delete
echo "Database backup written to $BACKUP_DIR/postgres-$STAMP.sql.gz"
