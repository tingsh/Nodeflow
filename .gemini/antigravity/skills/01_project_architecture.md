# Skill: Project Architecture & Codebase Map

## Metadata
- **ID:** 01_project_architecture
- **Description:** Complete map of the Nodeflow Cloud and Edge repositories, app inventory, data hierarchy, and system architecture.
- **Scope:** Use this skill whenever you need to understand where a file should live, how the apps relate, or how data flows through the system.

---

## 1. System Overview
Nodeflow is a multi-tenant Industrial IoT SaaS platform. It consists of:
1. **Nodeflow Cloud:** Django-based control plane, telemetry ingestion, and dashboard.
2. **Nodeflow Edge:** Python-based gateway software for local protocol conversion (Modbus, OPC-UA, etc.).

## 2. Codebase Structure (Nodeflow Cloud)
The project follows a standard Django structure with the following key directories:
- `apps/`: Contains all business logic apps (18 total).
- `iot_platform/`: Core settings, WSGI/ASGI, and base URL configuration.
- `templates/`: Global templates and app-specific partials.
- `static/`: Global CSS/JS and marketing assets.
- `docs/`: System documentation and architecture ADRs.

### App Inventory (Key Apps)
- **`devices`**: Core models for Sites, Gateways, and Devices. Handles provisioning.
- **`telemetry`**: Ingestion and storage of time-series data using TimescaleDB.
- **`alerts`**: Rule engine and notification logic.
- **`dashboard`**: Main operational views and KPI aggregates.
- **`teams`**: Multi-tenancy and RBAC logic (Pegasus-based).
- **`onboarding`**: User and gateway setup wizards.
- **`automations`**: Logic for reacting to telemetry patterns (Cloud PLC).
- **`maintenance`**: Ticketing and preventive maintenance schedules.

## 3. Data Model Hierarchy
Multi-tenancy is enforced at the `Team` level.
`Team` → `Site` → `Gateway` → `Device` → `TelemetryData`

- All multi-tenant models must extend `apps.teams.models.BaseTeamModel`.
- Queries must always be scoped to the current team: `Model.objects.filter(team=request.team)`.

## 4. Technology Stack
- **Backend:** Django (Python 3.12+), PostgreSQL + TimescaleDB extension.
- **Frontend:** HTMX, Alpine.js, Tailwind CSS, DaisyUI.
- **Infrastructure:** Redis (caching/task queue), Celery (background tasks), Mosquitto (MQTT broker).

## 5. Service Layer Pattern
We do **not** put business logic in Views or Models. All logic belongs in a `services.py` file within each app.
- **Models:** Data definitions and basic helper methods only.
- **Views:** Request/Response handling, permission checks, and data preparation.
- **Services:** Complex operations, calculations, and cross-app logic.
