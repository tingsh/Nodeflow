# Novena Project Status

## Current Stage
- Phase: Pre-Launch / Release Candidate.
- Status: Core platform features, advanced AI and automation features, gateway commissioning, and marketing content are largely built. Current work is final polish, reliability, billing enforcement, documentation, and production-like local stabilization.

## Current Sprint Goal
Final launch preparation, bug fixing, and platform stabilization across Novena Hub and Novena Gateway.

## What Is Built
- Novena Hub: multi-tenant Django SaaS, teams and RBAC, onboarding, devices, sites, gateways, telemetry ingestion, TimescaleDB storage, Redis and Celery buffering, WebSockets, dashboard widgets, alerts, automations, maintenance tickets, Wagtail marketing content, Stripe billing foundations, and AI insights.
- Novena Gateway: Python gateway daemon, Modbus connector support, remote config handling, RPC, attribute sync, payload formatting, offline buffering, discovery, logging, network watchdog, and service/install files.
- Local development: WSL-native Hub stack is the preferred path with PostgreSQL and TimescaleDB, Redis, Mosquitto, Django, Celery worker, Celery Beat, MQTT consumer, and Vite.

## High-Priority Roadmap
1. Launch preparation: load testing, security review, production deployment checks, and hardware bug bash.
2. Billing and tiers: finish Stripe enforcement for subscription limits and plan-gated latency/features.
3. User documentation: customer setup docs, gateway onboarding docs, and API/telemetry docs.
4. Mobile polish: ensure device pages, dashboards, and operational forms work cleanly on tablet/mobile.

## Recent Activity Log
- 2026-07-02 (Codex Skill Migration): Migrated active project guidance from Antigravity-style loose Markdown files to Codex repo skills under .agents/skills in both Novena Hub and Novena Gateway. Archived historical Antigravity skill files under docs/archive/antigravity_skills_2026-07-02/, refreshed AGENTS.md to point at Codex skills, and added focused skills for project status, Hub architecture, WSL development workflow, telemetry/gateway protocol, UI/product design, product strategy, and Gateway runtime.
- 2026-07-02 (Telemetry Freshness Stabilization): Updated gateway freshness display to compute gateway online/offline from last_seen heartbeat age instead of trusting stale stored status alone. Updated device detail fallback polling to use the team latency limit default of 10 seconds. Added tests for gateway freshness, stale gateway context, fallback interval, and Gateway device_id payload propagation. Pushed Hub commit 36b5acf and Gateway commit 6c095c7.
- 2026-07-02 (Signup Required Label): Updated TeamSignupForm.team_name to render Company / Team Name (required), verified browser rendering and native required behavior, and ran Django checks plus syntax compilation.
- 2026-07-02 (Signup Company Validation UX): Added browser-side required behavior for team signup name while keeping server-side blank validation. Focused signup tests timed out during test database setup before completion.
- 2026-07-02 (Wagtail Homepage Template Repair): Added templates/content/novena_home_page.html so the public homepage returns HTTP 200 instead of TemplateDoesNotExist.
- 2026-07-02 (Local Dev Stack Restart): Verified WSL-native local stack: PostgreSQL/TimescaleDB, Redis, Mosquitto, Django, Vite, Celery worker, Celery Beat, and MQTT consumer.
- 2026-07-02 (Novena Platform Rename): Renamed cloud package to novena_hub and edge package/service to novena_gateway / novena-gateway, refreshed branding/config/docs/templates, and verified migrations, Django checks, focused tests, frontend type-check, and gateway compile checks.
- 2026-06-27 (Gateway Claim + Assisted Commissioning): Added gateway inventory and lifecycle states, moved claim flow into service logic, generated Cloud-to-Edge Modbus config with deviceId, and updated Edge remote config behavior.
- 2026-06-27 (WSL Post-Migration Health Check): Confirmed Hub WSL services, Django, Vite, Redis, PostgreSQL, Celery, Mosquitto, MQTT consumer, and type-check were healthy. Gateway runtime still needed WSL dependency installation.
- 2026-06-26 (WSL-Native Project Migration): Moved active Hub working copy to /home/shouheng/projects/Novena-Hub, reused ~/.venvs/novena, installed dependencies, and documented the WSL local development path.
