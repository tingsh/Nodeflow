# Novena Production Readiness Kit

Governed control adds mandatory signing-key, current-policy acknowledgement, audit-retention, Gateway clock/journal/storage, emergency-disable and restore-reset gates. See `docs/governed_remote_control_operations.md`.

This guide documents the repo-backed assets that help deploy Novena Hub safely on a low-cost single VPS.

It does not replace the production deployment plan. Use that plan for the cloud/vendor setup. Use this kit for the concrete files, checks, and operational guardrails that live in the codebase.

## Current Architecture Summary

Novena Platform has two runtime parts:

- Novena Hub: Django SaaS app for onboarding, dashboards, telemetry, alerts, automations, maintenance, billing, AI, SES email, and WhatsApp.
- Novena Gateway: Python edge runtime on Raspberry Pi CM4-class hardware that sends field telemetry to Hub through MQTT.

The first production target is a lean VPS deployment:

- Django ASGI web app through Gunicorn/Uvicorn.
- PostgreSQL with TimescaleDB for relational and time-series data.
- Redis for cache, Celery, and Channels.
- Celery worker and Celery Beat for background and scheduled jobs.
- Celery Beat must include `apps.devices.tasks.dispatch_due_remote_command_outboxes`; alert on dead-lettered command outbox rows and repeatedly expired leases.
- Celery Beat must include `apps.devices.tasks.dispatch_due_gateway_config_outboxes`; alert on dead-lettered configuration rows and repeatedly expired leases.
- MQTT consumer for gateway telemetry ingestion.
- Mosquitto with Dynamic Security for gateway credentials.
- Host Nginx for HTTPS and WebSocket reverse proxy.

Teacher note: ASGI is the Python web interface that supports both normal HTTP requests and long-lived WebSocket connections. Novena uses WebSockets for live telemetry, so production should not use a plain WSGI-only server.

## Deployment Asset Map

Production files added by this kit:

- `Dockerfile.prod`: production app image with frontend build and Python prod dependencies.
- `docker-compose.prod.yml`: production service graph for web, worker, beat, MQTT consumer, Postgres, Redis, and Mosquitto.
- `deploy/env/production.env.example`: safe placeholder env file.
- `deploy/nginx/novena.conf.example`: host Nginx reverse proxy example.
- `deploy/mosquitto/mosquitto.prod.conf`: Mosquitto production listener config.
- `deploy/mosquitto/dynamic-security.example.json`: empty seed file; initialize real credentials before production.
- `deploy/backups/*.sh`: Postgres and private-report backup, restore, and retention scripts.
- `deploy/systemd/*.example`: nightly backup timer examples.
- `docs/production_backup_restore.md`: backup and restore walkthrough.

Do not commit `deploy/env/production.env` or real Mosquitto credential files with secrets.

## Required DNS Records

Use Cloudflare DNS:

| Host | Type | Target | Cloudflare mode |
| --- | --- | --- | --- |
| `novenaplatform.com` | A | VPS IP | Proxied |
| `www.novenaplatform.com` | CNAME | `novenaplatform.com` | Proxied |
| `app.novenaplatform.com` | A | VPS IP | Proxied |
| `mqtt.novenaplatform.com` | A | VPS IP | DNS only |

Use DNS-only for MQTT because standard Cloudflare proxying is for HTTP(S), not raw MQTT.

## Required Environment Variables

Start from:

```bash
cp deploy/env/production.env.example deploy/env/production.env
```

Then fill real values for:

- Django: `SECRET_KEY`, `ALLOWED_HOSTS`, `APP_BASE_URL`, `HEALTH_CHECK_TOKENS`.
- Database: `POSTGRES_PASSWORD`, `DATABASE_URL`.
- MQTT: `MQTT_DYNSEC_ADMIN_USER`, `MQTT_DYNSEC_ADMIN_PASS`, `GATEWAY_CLAIM_SECRET`.
- Public gateway instructions: `PUBLIC_MQTT_BROKER_HOST=mqtt.novenaplatform.com`, `PUBLIC_MQTT_BROKER_PORT=8883`.
- SES: `AWS_SES_ACCESS_KEY_ID`, `AWS_SES_SECRET_ACCESS_KEY`, sender emails.
- WhatsApp: Meta phone ID, access token, verify token, approved alert template.
- Stripe: keep `STRIPE_LIVE_MODE=False` for unpaid pilots; configure live keys before paid launch.
- Sentry: strongly recommended before pilots.

### Guided Setup configuration delivery

Guided Setup uses the same Ed25519 signing authority as governed remote commands. Set
`GATEWAY_CONFIG_ENVELOPE_TTL_SECONDS` between 60 and 900 seconds and
`GATEWAY_CONFIG_OUTBOX_MAX_ATTEMPTS` between 1 and 10. Celery Beat must run
`apps.devices.tasks.dispatch_due_gateway_config_outboxes` so queued or abandoned
delivery leases recover after worker restarts. Set
`GUIDED_SETUP_FIRST_TELEMETRY_TIMEOUT_SECONDS` to the longest normal interval
before a newly activated device should report data; the default is 180 seconds.

Before enabling `guided_setup_v1` on a Gateway:

1. Install the Hub signing public key under the Gateway RPC
   `trusted_command_keys` setting.
2. Confirm the Gateway reports a trusted clock and writable configuration journal.
3. Prove a failed connector activation restores the last-known-good configuration.
4. Confirm the Hub receives matching revision, checksum, and idempotency evidence.

Until those checks pass, the Gateway does not advertise the capability and Hub keeps
using the compatible legacy setup path. Never copy a Hub private signing key to a
Gateway.

## First Server Build

From the Hub repo on the VPS:

```bash
docker compose -f docker-compose.prod.yml config
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d postgres redis mosquitto
docker compose -f docker-compose.prod.yml run --rm web python manage.py migrate
docker compose -f docker-compose.prod.yml run --rm web python manage.py verify_timescale
docker compose -f docker-compose.prod.yml run --rm web python manage.py collectstatic --noinput
docker compose -f docker-compose.prod.yml up -d
```

Then configure host Nginx using `deploy/nginx/novena.conf.example`.

## Mosquitto Dynamic Security

The production Mosquitto config expects a real `deploy/mosquitto/data/dynamic-security.json`.

Do not use the development credential file from `mosquitto/dynamic-security.json`.

Create production credentials using Mosquitto Dynamic Security tooling, then ensure:

- Hub internal services can publish/subscribe on internal listener `1883`.
- Dynamic Security admin credentials match `MQTT_DYNSEC_ADMIN_USER` and `MQTT_DYNSEC_ADMIN_PASS`.
- Gateways connect publicly through `mqtt.novenaplatform.com:8883`.
- Port `1884` is private and not exposed through the VPS firewall.

## Production Readiness Command

Run:

```bash
docker compose -f docker-compose.prod.yml run --rm web python manage.py production_readiness_check
```

For machine-readable output:

```bash
docker compose -f docker-compose.prod.yml run --rm web python manage.py production_readiness_check --json
```

The command fails on blockers such as:

- `DEBUG=True`
- default Django secret
- default gateway claim secret
- wildcard `ALLOWED_HOSTS`
- missing TimescaleDB hypertable
- missing Redis/MQTT connectivity
- default MQTT Dynamic Security admin credentials
- missing SES, WhatsApp, or health check token settings

Warnings are allowed for unpaid pilots, especially Stripe test mode. Treat missing Sentry as a strong warning, not a blocker.

## Backup And Restore

Read `docs/production_backup_restore.md` before inviting pilots.

Minimum routine:

```bash
./deploy/backups/backup_postgres.sh
./deploy/backups/backup_private_media.sh
./deploy/backups/backup_retention.sh
```

First restore drill:

```bash
RESTORE_DATABASE_URL=postgresql://novena:<password>@localhost:5432/novena_restore_test \
BACKUP_FILE=/opt/novena/Novena-Hub/backups/postgres/daily/<backup>.dump.gz \
RESTORE_CONFIRM=restore-now \
./deploy/backups/restore_postgres.sh
```

Teacher note: a backup is the file. A restore drill is proof that the file can actually bring Novena back.

## Go-Live Smoke Test

Before inviting customers:

1. `https://novenaplatform.com` loads the public site.
2. `https://app.novenaplatform.com` loads login/signup.
3. `/health/?token=<token>` returns healthy.
4. `production_readiness_check` has no `FAIL` results.
5. WebSocket live telemetry works on a device page.
6. Gateway connects to `mqtts://mqtt.novenaplatform.com:8883`.
7. Gateway claim, discovery, config push, telemetry, alert, email, WhatsApp, and maintenance ticket flow works end-to-end.
8. SES sends from the production sender.
9. WhatsApp webhook verifies against the public HTTPS app domain.
10. Backup runs and restore drill has passed.

## Hardware Replay Handoff

While production setup is happening, hardware replay should prove this path:

```text
field device -> Novena Gateway -> mqtt.novenaplatform.com:8883 -> Mosquitto -> mqtt_consumer -> TimescaleDB -> dashboard -> alert -> email/WhatsApp -> maintenance ticket
```

Do not use `pilot_readiness_audit keepalive` during hardware replay. Physical gateways must prove heartbeat, discovery, telemetry, alerting, and recovery themselves.

## Rollback Basics

For normal bad deploy:

1. Revert to the previous Git SHA.
2. Rebuild the web image.
3. Restart web, worker, beat, and MQTT consumer.

For bad database migration:

1. Stop web, worker, beat, and MQTT consumer.
2. Take a backup of the broken current state.
3. Restore the last known good backup only if needed.
4. Deploy the matching code version.
5. Run migrations and readiness checks.

Avoid database restore for ordinary UI bugs. Restoring the database rewinds customer data.

## Upgrade Path

This kit is intentionally lean. Around 20 paying customers, or sooner if customers rely on Novena operationally, plan to:

- migrate Postgres/TimescaleDB to a managed database if extension support fits;
- move media to object storage;
- add GitHub Actions deployment with manual approval;
- add external uptime monitoring;
- consider a separate MQTT VPS if gateway traffic grows.
