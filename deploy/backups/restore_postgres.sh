#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${NOVENA_ROOT:-/opt/novena/Novena-Hub}"
ENV_FILE="${NOVENA_ENV_FILE:-$ROOT_DIR/deploy/env/production.env}"
BACKUP_FILE="${BACKUP_FILE:-${1:-}}"
TARGET_DATABASE_URL="${RESTORE_DATABASE_URL:-${DATABASE_URL:-}}"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
  TARGET_DATABASE_URL="${RESTORE_DATABASE_URL:-${DATABASE_URL:-$TARGET_DATABASE_URL}}"
fi

if [[ -z "$BACKUP_FILE" || ! -f "$BACKUP_FILE" ]]; then
  echo "Usage: BACKUP_FILE=/path/to/backup.dump.gz RESTORE_CONFIRM=restore-now $0" >&2
  echo "Or pass the backup path as the first argument." >&2
  exit 1
fi

if [[ -z "$TARGET_DATABASE_URL" ]]; then
  echo "DATABASE_URL or RESTORE_DATABASE_URL is required." >&2
  exit 1
fi

if [[ "${RESTORE_CONFIRM:-}" != "restore-now" ]]; then
  echo "Refusing to restore without RESTORE_CONFIRM=restore-now." >&2
  echo "Restores can overwrite data. Test on a disposable database first." >&2
  exit 1
fi

echo "Restoring $BACKUP_FILE into target database."
gzip -dc "$BACKUP_FILE" | pg_restore --clean --if-exists --no-owner --no-acl --dbname "$TARGET_DATABASE_URL"
echo "Restore complete."
