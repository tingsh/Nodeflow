# Novena Production Backup And Restore Guide

This guide is for the first low-cost production deployment where Novena runs Postgres/TimescaleDB on the same VPS as the app.

## Mental Model

A backup is a copy of the database at a point in time. A restore is the act of loading that backup into a database again.

The important part is the restore. Until we have restored a backup once, we only have a file that we hope is useful.

## What The Scripts Do

- `deploy/backups/backup_postgres.sh` creates a compressed custom-format `pg_dump`.
- `deploy/backups/restore_postgres.sh` restores one selected backup into a target database.
- `deploy/backups/backup_retention.sh` keeps local backup storage from growing forever.
- The systemd examples run the backup nightly.

The backup script reads `DATABASE_URL` from `deploy/env/production.env` by default. If `BACKUP_RCLONE_REMOTE` is set, it also uploads the backup tree with `rclone`.

## First Setup

On the VPS:

```bash
sudo apt-get update
sudo apt-get install -y postgresql-client gzip rclone
cd /opt/novena/Novena-Hub
chmod +x deploy/backups/*.sh
```

Create the first backup manually:

```bash
NOVENA_ROOT=/opt/novena/Novena-Hub ./deploy/backups/backup_postgres.sh
```

If using Cloudflare R2 or Backblaze B2, configure `rclone` and add this to `deploy/env/production.env`:

```env
BACKUP_RCLONE_REMOTE=novena-r2:novena-production-backups/postgres
```

## Restore Drill

Do the first restore into a disposable database, not production.

```bash
createdb novena_restore_test
RESTORE_DATABASE_URL=postgresql://novena:<password>@localhost:5432/novena_restore_test \
BACKUP_FILE=/opt/novena/Novena-Hub/backups/postgres/daily/<backup-file>.dump.gz \
RESTORE_CONFIRM=restore-now \
./deploy/backups/restore_postgres.sh
```

Then inspect the restored database:

```bash
psql postgresql://novena:<password>@localhost:5432/novena_restore_test
```

Check that important tables exist:

```sql
\dt
select count(*) from teams_team;
select count(*) from devices_gateway;
select count(*) from telemetry_telemetrydata;
```

Drop the disposable database only after the restore is verified:

```bash
dropdb novena_restore_test
```

## Nightly Timer

Copy the examples:

```bash
sudo cp deploy/systemd/novena-postgres-backup.service.example /etc/systemd/system/novena-postgres-backup.service
sudo cp deploy/systemd/novena-postgres-backup.timer.example /etc/systemd/system/novena-postgres-backup.timer
sudo systemctl daemon-reload
sudo systemctl enable --now novena-postgres-backup.timer
```

Check timer status:

```bash
systemctl list-timers novena-postgres-backup.timer
journalctl -u novena-postgres-backup.service -n 100 --no-pager
```

## If Backup Fails

1. Check disk space: `df -h`.
2. Check database connectivity from the server.
3. Run the backup script manually and read the first error.
4. Check `rclone` remote credentials if upload failed.
5. Do not invite more pilot customers until backup is healthy again.

## Restore Into Production

Only restore production when data is corrupted or a migration caused irreversible damage. A restore rewinds the database to the backup time, so newer customer data may be lost.

Before production restore:

1. Stop `web`, `celery-worker`, `celery-beat`, and `mqtt-consumer`.
2. Take one final backup of the current broken state.
3. Restore the selected backup with `RESTORE_CONFIRM=restore-now`.
4. Run migrations only if the code version requires them.
5. Start services and run `python manage.py production_readiness_check`.
