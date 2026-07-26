#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${NOVENA_ROOT:-/opt/novena/Novena-Hub}"
BACKUP_ROOT="${NOVENA_BACKUP_DIR:-$ROOT_DIR/backups/postgres}"
PRIVATE_MEDIA_BACKUP_ROOT="${NOVENA_PRIVATE_MEDIA_BACKUP_DIR:-$ROOT_DIR/backups/private_media}"

mkdir -p "$BACKUP_ROOT/daily" "$BACKUP_ROOT/weekly" "$BACKUP_ROOT/monthly"
mkdir -p \
  "$PRIVATE_MEDIA_BACKUP_ROOT/daily" \
  "$PRIVATE_MEDIA_BACKUP_ROOT/weekly" \
  "$PRIVATE_MEDIA_BACKUP_ROOT/monthly"

echo "Applying local backup retention under $BACKUP_ROOT"
find "$BACKUP_ROOT/daily" -type f -name '*.dump.gz' -mtime +7 -delete
find "$BACKUP_ROOT/weekly" -type f -name '*.dump.gz' -mtime +35 -delete
find "$BACKUP_ROOT/monthly" -type f -name '*.dump.gz' -mtime +100 -delete
find "$PRIVATE_MEDIA_BACKUP_ROOT/daily" -type f -name '*.tar.gz' -mtime +7 -delete
find "$PRIVATE_MEDIA_BACKUP_ROOT/weekly" -type f -name '*.tar.gz' -mtime +35 -delete
find "$PRIVATE_MEDIA_BACKUP_ROOT/monthly" -type f -name '*.tar.gz' -mtime +100 -delete

echo "Retention complete. Configure lifecycle rules separately in Cloudflare R2 or Backblaze B2."
