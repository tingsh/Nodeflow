# Novena Hub

Novena Hub is the Django control plane for Novena Platform. It provides tenant-scoped onboarding, fleet and device management, MQTT telemetry ingestion, dashboards, alerts, automations, maintenance workflows, governed remote control, billing foundations and business-impact reporting.

Novena Gateway is maintained in the sibling `Novena-Gateway` repository and runs on Raspberry Pi CM4-class edge hardware.

## Start here

- [Documentation authority index](docs/README.md)
- [Current project status](docs/agent_context/skills/novena-project-status/references/project_status.md)
- [Production readiness kit](docs/production_readiness_kit.md)
- [Production backup and restore](docs/production_backup_restore.md)

Historical brainstorming, completed implementation plans and superseded reviews live under `docs/archive/`. They are retained for context but are not current implementation guidance.

## Local development

The supported development path on this machine is WSL-native. PostgreSQL/TimescaleDB, Redis, Mosquitto, Django, Celery and Vite run as native WSL services; Docker is reserved for deployment validation.

```bash
cd /home/shouheng/projects/Novena-Hub
source /home/shouheng/.venvs/novena/bin/activate
uv sync --frozen
npm ci
make local-check
```

Use the repository helpers for focused work:

```bash
make local-manage ARGS="makemigrations --check --dry-run"
make local-test ARGS="apps.devices.tests.test_onboarding --keepdb"
make local-pytest ARGS="apps/devices/tests/test_infrastructure.py -q"
npm run type-check -- --pretty false
npm run build
```

The full local stack workflow and troubleshooting notes are maintained in the repo-local `novena-hub-development-workflow` and `novena-local-dev` skills under `.agents/skills/`.

## Production reference

Production uses the assets in `Dockerfile.prod`, `docker-compose.prod.yml` and `deploy/`. Before shipping a behavior change, run the production-readiness checks described in the documentation index and review whether environment, proxy, MQTT, backup or rollback guidance must change.

## Generated and inherited assets

- Django migrations, the generated TypeScript API client, compiled locale files and production static assets are intentionally tracked.
- The SaaS Pegasus Stripe CLI archive and executable are intentionally retained for billing setup.
- Local virtual environments, dependencies, logs, caches, media and compiled development assets are ignored.
