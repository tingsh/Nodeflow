# Skill: Project Status & Roadmap

## Metadata
- **ID:** 07_project_status
- **Description:** Living record of the current build state, completed features, and high-priority roadmap items.
- **Scope:** Use this skill at the start of every session to understand "where we are" and at the end of every session to update "what we did."

---

## 1. Current Stage
- **Phase:** Phase 1 (Demoable MVP)
- **Status:** ~65% of core MVP functionality built.

## 2. What's Built (✅)
- **Multi-Tenancy:** Pegasus-based teams and RBAC (5 roles).
- **Core Models:** Sites, Gateways, Devices, Telemetry, Alerts, Tickets.
- **Data Pipeline:** MQTT ingestion to TimescaleDB.
- **Alert Engine:** Threshold rules and multi-channel notifications (Email/Webhook).
- **Onboarding:** 4-step wizard for new users and gateway provisioning.
- **Bidirectional MQTT:** RPC command bridge, config push, and remote logging.
- **Admin Tools:** Gateway claim-code logic and MQTT credential management.

## 3. High-Priority Roadmap (❌)
*Items are in order of execution priority.*

1. **IoT Command Center:** Transform `team_home` into a real-time operational dashboard with fleet-wide KPIs.
2. **Device Detail Charts:** Integrate Chart.js for real-time and historical telemetry visualization.
3. **Marketing Site:** Build the Wagtail-powered multi-page marketing site.
4. **Maintenance UI:** Complete the frontend for the Ticketing and PM Scheduling system.
5. **Automation Engine:** Build the "Cloud PLC" rule builder UI.
6. **Mobile Pass:** Ensure all dashboards are responsive for tablet/mobile.

## 4. Current Sprint Goal
**Focus:** Finalizing the "Market Ready" look and feel for Nodeflow Cloud.

## 5. Recent Activity Log
- **2026-05-15:** Initialized the AI Agent Skills System. Created Skill 01 (Architecture), Skill 02 (Conventions), and Skill 07 (Status). Refactored AGENTS.md into a lightweight loader.
- **2026-06-03:** Migrated the April 27 CTO Progress Review to the project `docs/` folder to persist context for future sessions.
- **2026-06-04:** Completed Phase 3 and Phase 4. Resolved the Django 5.x `timezone.utc` AttributeError in `mqtt_consumer.py`. Successfully ran the full End-to-End Local Loopback Simulation (Modbus TCP Sensor -> Nodeflow Edge -> local MQTT Broker -> Django Consumer -> TimescaleDB). Verified dashboard ingestion in browser and completed a comprehensive CTO Technical Audit.
