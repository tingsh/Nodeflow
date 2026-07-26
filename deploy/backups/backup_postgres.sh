#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${NOVENA_ROOT:-/opt/novena/Novena-Hub}"
ENV_FILE="${NOVENA_ENV_FILE:-$ROOT_DIR/deploy/env/production.env}"
BACKUP_ROOT="${NOVENA_BACKUP_DIR:-$ROOT_DIR/backups/postgres}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DB_URL="${DATABASE_URL:-}"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
  DB_URL="${DATABASE_URL:-$DB_URL}"
fi

if [[ -z "$DB_URL" ]]; then
  echo "DATABASE_URL is required. Set it in the environment or $ENV_FILE." >&2
  exit 1
fi

mkdir -p "$BACKUP_ROOT/daily" "$BACKUP_ROOT/weekly" "$BACKUP_ROOT/monthly"

BACKUP_FILE="$BACKUP_ROOT/daily/novena_hub_${TIMESTAMP}.dump.gz"

echo "Creating Postgres backup: $BACKUP_FILE"
pg_dump --format=custom --no-owner --no-acl "$DB_URL" | gzip -9 > "$BACKUP_FILE"

if [[ "$(date -u +%u)" == "7" ]]; then
  cp "$BACKUP_FILE" "$BACKUP_ROOT/weekly/"
fi

if [[ "$(date -u +%d)" == "01" ]]; then
  cp "$BACKUP_FILE" "$BACKUP_ROOT/monthly/"
fi

if [[ -n "${BACKUP_RCLONE_REMOTE:-}" ]]; then
  echo "Uploading backup tree to rclone remote: $BACKUP_RCLONE_REMOTE"
  rclone copy "$BACKUP_ROOT" "$BACKUP_RCLONE_REMOTE"
fi

echo "Backup complete: $BACKUP_FILE"
