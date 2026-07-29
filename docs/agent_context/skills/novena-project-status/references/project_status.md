# Novena Project Status

## Current Stage

- Phase: Pre-Launch / Release Candidate.
- Status: The four Managed Gateway software hardening blockers and customer-facing polish are implemented and locally verified on the hardening branch. Physical CM4 replay and a 3–5 customer technical canary remain release gates.

## Current Sprint Goal

Review and merge the Managed Gateway hardening changes, then run the three vertical CM4 hardware replays before widening the pilot.

## Open Release Gates

1. Validate offline buffering across process restart and reconnect on physical CM4 hardware.
2. Run factory-energy, cold-chain and facilities/HVAC CM4 hardware replays with representative equipment.
3. Validate governed write-back on representative devices, including power loss, key rotation, restore and emergency-disable recovery.
4. Configure and validate production Stripe webhooks/live billing and inbound WhatsApp security before paid rollout.
5. Qualify a 3–5 customer technical canary before the planned 20-customer cohort.

## Current Sources of Truth

- Documentation authority: `docs/README.md`.
- Hub architecture and protocol: repo-local skills under `.agents/skills/`.
- Gateway runtime: the Gateway repository's `ARCHITECTURE.md` and repo-local skills.
- Production operations: `docs/production_readiness_kit.md`, `docs/production_backup_restore.md` and feature-specific operator guides.

## Recent Activity Log

- 2026-07-29: Documented the preferred Novena GitHub workflow in the local development skill: keep local `git` for branches, diffs, staging and commits; prefer the connected GitHub plugin for PR creation, CI/check inspection, review handling and merges; use `gh` only as a fallback; never print or embed GitHub token values in commands or repository files.
- 2026-07-28: Restored the small vertical outcome-pack review fixes on a focused branch: General IoT is the default onboarding profile, risky cold-chain/energy wording is softened, General IoT template ranking stays neutral, and curated cold-room/HVAC templates plus focused onboarding tests cover the behavior. Validation passed focused onboarding tests, Django checks, migration drift check and Ruff on touched files. Larger outcome-pack refactor work was intentionally left out.
- 2026-07-28: Completed the bounded Managed Gateway technical hardening implementation and customer-facing polish: fail-closed verified credential revocation and fresh-row reclaim, automatic activation recovery, signed durable configuration delivery with exact acknowledgements, plan-safe polling reconciliation, clearer lifecycle/configuration labels, manager-friendly RPC history, and visible recovery actions. Validation passed 300 Hub tests with one expected skip and 13 subtests, 110 Gateway tests, Ruff, Django and migration checks, frontend production build, template compilation, and a real temporary Mosquitto Dynamic Security provision/revoke/idempotency smoke. Physical CM4 replay remains open.
- 2026-07-27: Completed a software-only Managed Gateway + Cloud Hub end-to-end review across team/site onboarding, claim and activation, status/freshness, signed config delivery, simulated telemetry, logs/RPC, failure handling, tenant isolation and plan enforcement. Safely hardened immutable Gateway identity/status editing, stale onboarding status copy, device-limit enforcement across alternate onboarding paths, ambiguous multi-device telemetry identity handling and the plan-limit upgrade link. Validation passed: 305 Django tests with one expected skip, 110 Gateway tests, frontend type-check/build, Django checks and migration check, three-persona pilot simulation/UI route smoke, and a real local MQTT broker-to-buffer-to-database telemetry probe. Controlled-canary gaps remain around fail-open credential deprovisioning on Gateway release, activation recovery after its 24-hour window, legacy config acknowledgement semantics, plan-safe edge polling and physical CM4 replay.
- 2026-07-27: Completed the operator-language product polish across remote-control safety, Gateway setup and diagnostics, Business Impact, alerts, maintenance, automations and directly affected public product copy. Added customer-safe translations for current and historical control states/errors while preserving stored values, permissions, calculations, audit exports and MQTT/RPC contracts. Validation passed: Django checks, no-migration check, 85 focused Django tests plus the alert pytest module, the complete 301-test Django suite with one expected skip, frontend build/type-check, pre-commit, documentation links and repository hygiene.
- 2026-07-26: Completed a cleanup-only Hub and Gateway hygiene pass: archived stale planning documents, clarified documentation authority, removed runtime snapshots from Git tracking, strengthened repository checks and verified 294 Hub tests plus 110 Gateway tests. No production modules, schemas, routes, MQTT/RPC contracts, Stripe binaries or protected ThingsBoard-derived paths changed.
- 2026-07-26: Merged Business Impact and ROI Release 1 behind its Waffle rollout flag, including versioned baselines, deterministic value calculations, reports, private storage/backup integration and production-readiness gates. The full Hub suite passed 293 tests with one expected skip after merge.
- 2026-07-25: Completed guided Modbus commissioning and governed remote-control security/reliability across Hub and Gateway. Physical CM4 and representative equipment validation remains mandatory.
- 2026-07-22: Closed Hub quick-add tenant-isolation gaps and stabilized the WSL-native test commands.
- 2026-07-21: Enforced serial-scoped inbound MQTT identity and topic/payload serial validation across Hub and Gateway.
- 2026-07-20: Hardened the current hardware replay runbook and reproducible field-test release process.
- 2026-07-18: Updated the CTO assessment, business plan and pilot gates; the 20-customer handout remains on hold pending technical canary evidence.
- 2026-07-15: Added the production readiness kit, deployment assets and backup/restore baseline.
- 2026-07-13: Verified timezone-safe customer displays and approved WhatsApp alert-template delivery.

Full historical activity through 26 July 2026 is retained at `docs/archive/project_activity_2026_h1/project_status_full_history_2026-07-26.md` and should only be loaded for historical investigation.
