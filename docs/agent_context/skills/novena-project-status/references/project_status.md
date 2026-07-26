# Novena Project Status

## Current Stage

- Phase: Pre-Launch / Release Candidate.
- Status: Core Hub and Gateway capability is built. The Business Impact release, guided commissioning and governed-control hardening are merged, but physical CM4 replay, dependency-complete Gateway validation and a 3–5 customer technical canary remain release gates.

## Current Sprint Goal

Complete a behavior-preserving platform cleanup, then run reproducible Hub/Gateway validation and the three vertical CM4 hardware replays before widening the pilot.

## Open Release Gates

1. Complete dependency-clean Gateway tests and validate offline buffering across process restart and reconnect.
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

- 2026-07-26: Merged Business Impact and ROI Release 1 behind its Waffle rollout flag, including versioned baselines, deterministic value calculations, reports, private storage/backup integration and production-readiness gates. The full Hub suite passed 293 tests with one expected skip after merge.
- 2026-07-25: Completed guided Modbus commissioning and governed remote-control security/reliability across Hub and Gateway. Physical CM4 and representative equipment validation remains mandatory.
- 2026-07-22: Closed Hub quick-add tenant-isolation gaps and stabilized the WSL-native test commands.
- 2026-07-21: Enforced serial-scoped inbound MQTT identity and topic/payload serial validation across Hub and Gateway.
- 2026-07-20: Hardened the current hardware replay runbook and reproducible field-test release process.
- 2026-07-18: Updated the CTO assessment, business plan and pilot gates; the 20-customer handout remains on hold pending technical canary evidence.
- 2026-07-15: Added the production readiness kit, deployment assets and backup/restore baseline.
- 2026-07-13: Verified timezone-safe customer displays and approved WhatsApp alert-template delivery.

Full historical activity through 26 July 2026 is retained at `docs/archive/project_activity_2026_h1/project_status_full_history_2026-07-26.md` and should only be loaded for historical investigation.
