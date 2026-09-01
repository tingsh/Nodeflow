# Novena Hub Production Deployment Plan

Last reviewed: 2026-08-17

This is the practical plan for putting Novena Hub on a real public production server for a 3-5 customer technical canary, without creating a throwaway demo environment that must be rebuilt later.

The matching repo-backed checklist is `docs/production_readiness_kit.md`.

## CTO Recommendation

Use one low-cost VPS first, then graduate pieces out only when customer risk justifies it.

Recommended first production shape:

- One Ubuntu LTS VPS with Docker Compose.
- Host Nginx handles HTTPS for the public site and app.
- Docker Compose runs Django web, Celery worker, Celery Beat, MQTT consumer, Postgres/TimescaleDB, Redis, and Mosquitto.
- Cloudflare stays as DNS/CDN provider.
- Postgres/TimescaleDB stays self-hosted for the unpaid canary stage.
- Backups go to local disk plus an off-server rclone target such as Cloudflare R2 or Backblaze B2.

Teacher note: a VPS is a rented Linux server. It is cheaper because you operate more of the stack yourself. Managed services cost more because the provider handles pieces like backups, patching, failover, and scaling.

## Target Cost

For the first canary, aim for roughly USD 20-60/month before email/WhatsApp/Stripe variable usage:

- VPS: USD 12-40/month depending on RAM and disk.
- Backups/object storage: usually USD 1-10/month at this stage.
- Cloudflare DNS/CDN: USD 0/month on the Free plan for this use case.
- Domain: already owned.
- AWS SES, WhatsApp, Stripe: usage-based and likely small during pilots.

Use at least 4 GB RAM. Prefer 8 GB RAM if the price is still comfortable, because Postgres, Redis, Celery, WeasyPrint PDF generation, and Vite-built static assets all share the same machine.

## Domains

Use the common SaaS split you proposed:

- `novenaplatform.com`: public marketing site.
- `www.novenaplatform.com`: marketing alias.
- `app.novenaplatform.com`: Django app login, onboarding, dashboards, APIs, webhooks.
- `mqtt.novenaplatform.com`: public MQTT endpoint for gateways.

This is a good pattern. It keeps the marketing domain clean while giving the actual SaaS app its own operational hostname.

Cloudflare DNS records:

| Host | Type | Target | Cloudflare proxy |
| --- | --- | --- | --- |
| `novenaplatform.com` | A | VPS public IPv4 | Proxied |
| `www.novenaplatform.com` | CNAME | `novenaplatform.com` | Proxied |
| `app.novenaplatform.com` | A | VPS public IPv4 | Proxied |
| `mqtt.novenaplatform.com` | A | VPS public IPv4 | DNS only |

Keep MQTT as DNS only. Cloudflare's normal orange-cloud proxy is for HTTP/HTTPS traffic, not raw MQTT on port 8883.

## Server Layout

Use this production directory on the VPS:

```bash
/opt/novena/Novena-Hub
```

That path is intentionally separate from the local development checkout. Your current local development checkout is:

```bash
/home/shouheng/Novena-Platform/Novena-Hub
```

Teacher note: keeping `/opt/novena/Novena-Hub` on the VPS makes commands in systemd timers, backup scripts, and Nginx examples stable even if your laptop workspace moves again.

## Firewall

Allow only the ports customers and operators need:

```text
22/tcp    SSH admin access
80/tcp    HTTP for redirect and certificate challenge
443/tcp   HTTPS web app and WebSockets
8883/tcp  MQTT over TLS for gateways
```

Do not expose Postgres, Redis, Mosquitto `1883`, or Mosquitto Dynamic Security `1884` to the public internet. In the Compose file those are private Docker-network services by default.

## Cloudflare SSL Mode

Set Cloudflare SSL/TLS mode to Full (strict) after the server has certificates.

There are two acceptable certificate paths:

1. Let's Encrypt certificates on the VPS with Certbot.
2. Cloudflare Origin Certificates for the HTTP app, plus a normal certificate chain for MQTT if the Gateway validates public trust roots.

For the first deployment, I recommend Let's Encrypt because it is easier to reason about and works with normal clients.

## Install Server Packages

On a fresh Ubuntu LTS VPS:

```bash
sudo apt-get update
sudo apt-get upgrade -y
sudo apt-get install -y ca-certificates curl git nginx certbot python3-certbot-nginx rclone postgresql-client gzip tar
```

Install Docker Engine and the Compose plugin using the official Docker instructions for Ubuntu. Then verify:

```bash
docker --version
docker compose version
```

Use a modern Docker Compose version. The production Compose file uses `env_file.required`, which needs a recent Compose v2 release. If your server Compose is old, upgrade Docker Compose before continuing.

## Clone And Prepare The Repo

```bash
sudo mkdir -p /opt/novena
sudo chown -R "$USER:$USER" /opt/novena
cd /opt/novena
git clone <your-github-repo-url> Novena-Hub
cd /opt/novena/Novena-Hub
```

Create runtime directories:

```bash
mkdir -p deploy/env deploy/mosquitto/data media private_media static_root backups/postgres backups/private_media
chmod +x deploy/backups/*.sh
```

Copy the production env template:

```bash
cp deploy/env/production.env.example deploy/env/production.env
chmod 600 deploy/env/production.env
```

Then edit it:

```bash
nano deploy/env/production.env
```

## Required Production Environment

Fill the real values in `deploy/env/production.env`. The most important groups are:

- Django security: `SECRET_KEY`, `DEBUG=False`, `ALLOWED_HOSTS`, `APP_BASE_URL`, `CSRF_TRUSTED_ORIGINS`, `HEALTH_CHECK_TOKENS`.
- Database: `POSTGRES_PASSWORD`, `DATABASE_URL`.
- Redis: `REDIS_URL`.
- MQTT: `MQTT_DYNSEC_ADMIN_USER`, `MQTT_DYNSEC_ADMIN_PASS`, `MQTT_PROVISIONING_REQUIRED=True`, `MQTT_ACCEPT_LEGACY_SHARED_INBOUND=False`.
- Gateway identity and activation: `GATEWAY_CLAIM_SECRET`, `GATEWAY_ACTIVATION_ENCRYPTION_KEY`.
- Public gateway instructions: `PUBLIC_MQTT_BROKER_SCHEME=mqtts`, `PUBLIC_MQTT_BROKER_HOST=mqtt.novenaplatform.com`, `PUBLIC_MQTT_BROKER_PORT=8883`.
- Guided Setup and governed control: `REMOTE_CONTROL_ACTIVE_SIGNING_KEY_ID`, `REMOTE_CONTROL_SIGNING_KEYS`, `GATEWAY_CONFIG_*`, `GUIDED_SETUP_FIRST_TELEMETRY_TIMEOUT_SECONDS`.
- Email: AWS SES keys, sender addresses, optional Anymail webhook secret.
- WhatsApp: Meta phone ID, access token, verify token, approved alert template.
- Stripe: test mode is acceptable for unpaid canaries; live keys and webhook secret are required before paid launch.
- Business Impact reports: leave `USE_S3_MEDIA=False` for the first VPS deployment unless you intentionally move media to object storage.
- OTA: leave `NOVENA_OTA_SIGNING_PRIVATE_KEY` blank if Gateway software updates are operationally disabled for pilots; configure it before using signed OTA.

Generate secrets with commands like:

```bash
openssl rand -base64 48
```

For `GATEWAY_ACTIVATION_ENCRYPTION_KEY`, use a Fernet key. One safe way on your dev machine or server is:

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

For `REMOTE_CONTROL_SIGNING_KEYS`, use an Ed25519 seed in JSON form. Example shape only:

```env
REMOTE_CONTROL_ACTIVE_SIGNING_KEY_ID=prod-2026-08
REMOTE_CONTROL_SIGNING_KEYS={"prod-2026-08":"replace-with-base64-ed25519-seed"}
```

Teacher note: signing keys prove that Hub created a command/config envelope. The Gateway stores the matching public key and rejects unsigned or wrong-key instructions.

## Certificates

Issue HTTPS certificates for the web domains:

```bash
sudo certbot --nginx -d novenaplatform.com -d www.novenaplatform.com -d app.novenaplatform.com
```

Issue a certificate for MQTT:

```bash
sudo certbot certonly --standalone -d mqtt.novenaplatform.com
```

If Certbot cannot bind port 80 because Nginx is running, temporarily use the Nginx plugin or stop Nginx during the MQTT certificate challenge.

The Compose file expects MQTT certificate files here:

```text
/etc/letsencrypt/live/mqtt.novenaplatform.com/fullchain.pem
/etc/letsencrypt/live/mqtt.novenaplatform.com/privkey.pem
```

## Mosquitto Dynamic Security

The production Mosquitto config expects:

```bash
deploy/mosquitto/data/dynamic-security.json
```

Do not use development broker credentials.

Create a real Dynamic Security file from `deploy/mosquitto/dynamic-security.example.json`, then add:

- one admin client matching `MQTT_DYNSEC_ADMIN_USER` and `MQTT_DYNSEC_ADMIN_PASS`;
- a `gateway` baseline role with no broad publish ACLs;
- optional cloud-internal credentials if you later require authentication on the internal listener.

Current Hub provisioning creates per-gateway operational and bootstrap roles dynamically. That means you should not manually grant gateways broad publish access to shared topics such as `v1/gateway/telemetry`.

Teacher note: Dynamic Security is Mosquitto's runtime user/role system. Hub uses it to create one MQTT identity per Gateway, then scopes that Gateway to its own serial-number topics.

## Nginx

Copy the example and adapt paths if needed:

```bash
sudo cp deploy/nginx/novena.conf.example /etc/nginx/sites-available/novena.conf
sudo ln -s /etc/nginx/sites-available/novena.conf /etc/nginx/sites-enabled/novena.conf
sudo nginx -t
sudo systemctl reload nginx
```

The Nginx config must preserve WebSocket headers. Novena uses WebSockets for live device detail pages; if those headers are missing, normal pages may load but live telemetry will degrade to polling.

## First Build And Database Setup

Validate the production service graph:

```bash
docker compose -f docker-compose.prod.yml config
```

Build the app image:

```bash
docker compose -f docker-compose.prod.yml build
```

Start the infrastructure services:

```bash
docker compose -f docker-compose.prod.yml up -d postgres redis mosquitto
```

Run migrations and Timescale verification:

```bash
docker compose -f docker-compose.prod.yml run --rm web python manage.py migrate
docker compose -f docker-compose.prod.yml run --rm web python manage.py verify_timescale
docker compose -f docker-compose.prod.yml run --rm web python manage.py collectstatic --noinput
```

Start the full stack:

```bash
docker compose -f docker-compose.prod.yml up -d
```

Check services:

```bash
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs --tail=100 web
docker compose -f docker-compose.prod.yml logs --tail=100 celery-worker
docker compose -f docker-compose.prod.yml logs --tail=100 mqtt-consumer
```

## Production Readiness Check

Run the app-level preflight:

```bash
docker compose -f docker-compose.prod.yml run --rm web python manage.py production_readiness_check
```

Run JSON output if you want a machine-readable record:

```bash
docker compose -f docker-compose.prod.yml run --rm web python manage.py production_readiness_check --json
```

Do not invite canary users while any `FAIL` remains. `WARN` can be acceptable for unpaid pilots when intentional, for example Stripe test mode.

## Backups

Set up local backup plus off-server upload. The current system needs both:

- Postgres/TimescaleDB backup for relational data and telemetry.
- Private media backup for confidential Business Impact PDF reports.

Subscription telemetry limits are access windows, not backup or database deletion schedules. PostgreSQL/TimescaleDB may still contain telemetry outside a team's current visible plan window until the global physical retention policy, currently 90 days, drops it.

Manual first backup:

```bash
NOVENA_ROOT=/opt/novena/Novena-Hub ./deploy/backups/backup_postgres.sh
NOVENA_ROOT=/opt/novena/Novena-Hub ./deploy/backups/backup_private_media.sh
NOVENA_ROOT=/opt/novena/Novena-Hub ./deploy/backups/backup_retention.sh
```

Install the timer:

```bash
sudo cp deploy/systemd/novena-postgres-backup.service.example /etc/systemd/system/novena-postgres-backup.service
sudo cp deploy/systemd/novena-postgres-backup.timer.example /etc/systemd/system/novena-postgres-backup.timer
sudo systemctl daemon-reload
sudo systemctl enable --now novena-postgres-backup.timer
```

Then perform one restore drill before inviting customers. A backup that has never been restored is only a hope, not a recovery plan.

## Go-Live Smoke Test

Before inviting the first 3-5 technical canary customers:

1. `https://novenaplatform.com` loads.
2. `https://app.novenaplatform.com` loads signup/login.
3. `https://app.novenaplatform.com/health/?token=<token>` returns healthy.
4. `production_readiness_check` has no `FAIL`.
5. Nginx WebSocket proxy works on a device detail page.
6. Mosquitto accepts a TLS MQTT connection on `mqtt.novenaplatform.com:8883`.
7. A test Gateway claims successfully and receives managed MQTT credentials.
8. Serial-scoped telemetry arrives on `v1/gateway/{serial}/telemetry` and lands under the correct tenant.
9. Guided Setup publishes signed config and receives matching acknowledgement evidence.
10. First telemetry appears on the customer dashboard.
11. Alert triggers and sends real SES email plus approved WhatsApp template.
12. Maintenance ticket flow works.
13. Backup and restore drill passed.
14. Stripe webhook signature validation is configured before any paid user is charged.

## Hardware Replay Handoff

The production server is not considered customer-ready until the physical replay proves:

```text
field device -> Novena Gateway -> mqtt.novenaplatform.com:8883 -> Mosquitto -> mqtt_consumer -> TimescaleDB -> dashboard -> alert -> email/WhatsApp -> maintenance ticket
```

For August 2026, the open release gates remain:

- offline buffering across process restart and reconnect on physical CM4;
- factory-energy, cold-chain, and facilities/HVAC replay with representative equipment;
- governed write-back validation including power loss, key rotation, restore, and emergency disable;
- production Stripe webhooks/live billing and inbound WhatsApp security before paid rollout;
- 3-5 customer technical canary before widening toward 20 customers.

## Deployment Update Routine

For normal code updates after the first deployment:

```bash
cd /opt/novena/Novena-Hub
git fetch origin
git checkout <release-sha-or-branch>
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml run --rm web python manage.py migrate
docker compose -f docker-compose.prod.yml run --rm web python manage.py collectstatic --noinput
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml run --rm web python manage.py production_readiness_check
```

Deploy web, worker, Beat, and MQTT consumer together. They share lifecycle states, outbox semantics, and acknowledgement fields.

## Rollback

For a bad UI or code deploy:

1. Revert to the previous known-good Git SHA.
2. Rebuild the image.
3. Restart web, worker, Beat, and MQTT consumer.
4. Run smoke tests again.

For a bad data migration:

1. Stop web, worker, Beat, and MQTT consumer.
2. Take a backup of the broken current state.
3. Restore the last known-good backup only if data is corrupted or unrecoverable.
4. Deploy the matching code version.
5. Run migrations and readiness checks.

Do not restore the database for ordinary UI bugs. Database restore rewinds customer data.

## When To Move Beyond One VPS

Stay on the single VPS through unpaid canaries if it is stable and backups are proven.

Move Postgres/TimescaleDB to managed infrastructure around 20 paying customers, or earlier if customers depend on Novena for daily operations. The trigger is not just traffic; it is responsibility. Once paying customers rely on the data, database backup, restore, patching, and monitoring become business-critical.
