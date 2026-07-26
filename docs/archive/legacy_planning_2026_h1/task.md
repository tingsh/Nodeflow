> **Historical reference — do not use as current implementation guidance.** See the [current project status](../../agent_context/skills/novena-project-status/references/project_status.md).

# Novena Feature Roadmap — Task Tracker

> **Started:** April 17, 2026  
> **Build Order:** RBAC → AI Chat → Write-Back → Shared Links → Maintenance → Automations

---

## Sprint 1: Role-Based Access Control (RBAC) — ✅ COMPLETE (Apr 17, 2026)

- [x] Expand `apps/teams/roles.py` with 5 roles + permissions map.
- [x] Add `has_permission(user, team, permission)` helper function.
- [x] Create `apps/teams/decorators.py` with `require_permission()` decorator.
- [x] Create `apps/teams/templatetags/team_permissions.py` with `{% has_perm %}` tag.
- [x] Write data migration: existing admin → owner, member → manager.
- [x] Apply `@require_permission()` to all existing views (alerts, devices, dashboard).
- [x] Update templates: conditionally show/hide buttons based on role.
- [x] Update team member management UI: role selector with descriptions.
- [x] Update invitation flow: allow inviting with specific roles.
- [x] Write unit tests for permission checks across all role/permission combos.
- [x] Manual testing: verified via browser — alerts, sites, team management all RBAC-correct.

---

## Sprint 2: AI "Chat With Your Data" — ✅ COMPLETE (Apr 17, 2026)

- [x] Create `apps/chat/system_prompt.py` with Novena-specific IIoT prompt
- [x] Create `apps/chat/tools.py` with OpenAI function/tool definitions
- [x] Create `apps/chat/tool_executor.py` with `NovenaToolExecutor` class
-   - [x] Implement `get_energy_data()` — TimescaleDB energy aggregates
-   - [x] Implement `get_device_status()` — current readings
-   - [x] Implement `get_alerts_summary()` — alert statistics
- [x] Add `ChatUsage` model — per-team monthly usage tracking
- [x] Modify `ChatConsumer` — add tool-calling loop (non-stream → tools → stream)
- [x] Inject team context into WebSocket consumer
- [x] Add per-tier usage limits (tracked via ChatUsage)
- [x] Add "suggested questions" chips in chat UI
- [x] Add usage counter display in chat header
- [x] Update `apps/chat/utils.py` for LLM provider config
- [x] Add unit tests for tool executor and usage tracking
- [x] Manual testing: verified end-to-end chat flow with tool calls

---

## Sprint 3: Write-Back / Remote Control Commands — ✅ COMPLETE (Apr 17, 2026)

- [x] Create `DeviceCommand` model (tracking: pending, sent, executed, failed)
- [x] Implement `apps/devices/services.py` for MQTT command publication
- [x] Adopt ThingsBoard Gateway standard for RPC (v1/gateway/rpc)
- [x] Update `mqtt_consumer.py` to listen for command responses
- [x] Update `DeviceTemplate` register map schema (add `writable: true`)
- [x] Create Control UI (Toggle for Bits, Slider for Integers)
- [x] Implement UI-side polling for command status (HTMX)
- [x] Add "Command Audit Trail" table in Device Detail view
- [x] Implement RBAC checks: only `Manager` and up can send commands
- [x] Integrated safety warnings in remote control UI
- [x] Verified end-to-end command/response flow with unit tests

---

## Sprint 4: Public Shareable Links — ✅ COMPLETE (Apr 18, 2026)

- [x] Add `SharedDashboard` model to `apps/dashboard/models.py`
- [x] Create public dashboard view (unauthenticated)
- [x] Create management views: list, create, delete shared links
- [x] Create `templates/dashboard/public_dashboard.html` — minimal, auto-refresh
- [x] Add "Powered by Novena" footer with CTA
- [x] Add optional password gate
- [x] Add expiry enforcement
- [x] Add view count tracking + analytics
- [x] Add `?kiosk=1` mode for TV screens
- [x] Add RBAC: `manage_shared_links` permission
- [x] URL routing: `/shared/<token>/` outside auth middleware
- [x] Write tests for public access, password, expiry
- [x] Manual testing: share link, open in incognito

---

## Sprint 5: Maintenance Ticketing — ✅ COMPLETE (Apr 18, 2026)

### Reactive (Alert-triggered)
- [x] Create `apps/maintenance/` Django app
- [x] Add `MaintenanceTicket` model (priority, status, assignment, resolution, downtime)
- [x] Add `TicketComment` model (threaded comments with file attachments)
- [x] Add `TicketTemplate` model (pre-built templates with checklists)
- [x] Create `auto_create_ticket(alert)` service
- [x] Hook into `alerts/services.py` `trigger_alert()` for warning/critical alerts
- [x] Ticket list view with tab filters (Open / In Progress / Waiting / Resolved / Closed)
- [x] Ticket detail view with timeline, comments, status transitions
- [x] Ticket create/edit forms
- [x] Assignment + notification (email/WhatsApp when assigned)

### Preventive (Scheduled)
- [x] Add `PreventiveSchedule` model (device, interval, checklist, next_due_at)
- [x] Create `generate_preventive_tickets()` Celery beat task (runs daily)
- [x] PM Schedule CRUD views
- [x] "Overdue PMs" warning on dashboard

### Dashboard Integration
- [x] Command Center widget: open tickets, avg response time, overdue PMs
- [x] RBAC: permissions for ticket management vs view-only

---

## Sprint 6: Logic & Cloud Automations — ✅ COMPLETE (Apr 18, 2026)

- [x] Create `apps/automations/` Django app
- [x] Add `Automation` model (trigger type, cooldown, active flag)
- [x] Add `AutomationCondition` model (device, key, operator, threshold, duration, AND/OR)
- [x] Add `AutomationAction` model (send_command, notify, webhook)
- [x] Add `AutomationLog` model (execution audit)
- [x] Build automation engine: `evaluate_automations(device, values)`
- [x] Redis-backed duration tracking for sustained conditions
- [x] Hook into `ingest_telemetry_data()` after alert checks
- [x] IFTTT-style visual builder UI
- [x] Dynamic device/key dropdowns populated from team data
- [x] Pre-built automation templates *(deferred for future polish, but structure exists)*
- [x] Execution logs view
- [x] Add "Supervisory only" disclaimer in UI
- [x] RBAC: `manage_automations`, `view_automations` permissions
- [x] Write tests: condition evaluation, duration tracking, action execution
- [x] Test with edge simulator (and later with real S7-1200)

---

## Phase 2: Cloud Platform Polish

---

## Sprint 7A: Dashboard Command Center Overhaul — ✅ COMPLETE (Apr 18, 2026)

- [x] Enrich `team_home` view with active alerts, device health, gateway health, automations count
- [x] Query real hourly energy data from TimescaleDB for fleet chart (last 24h)
- [x] Add Redis caching (60s TTL) for heavy dashboard queries
- [x] Redesign dashboard layout — 5-card KPI strip (Energy, Alerts, Devices, Tickets, Automations)
- [x] Replace fake fleet chart data with real hourly TimescaleDB data
- [x] Add Live Alert Feed panel (5 most recent alerts with severity badges)
- [x] Add Device Fleet Grid (top 8 devices with status, last reading, last seen)
- [x] Add Quick Actions panel (Add Hardware, Create Rule, Create Automation, View Reports)
- [x] Polish Site Navigator styling
- [x] Fix stray text at line 245 of app_home.html
- [x] Implement HTMX auto-refresh (60s trigger) for dashboard counters and feeds
- [x] Run tests + visual verification

---

## Sprint 7B: Multi-Page Marketing Website — ✅ COMPLETE (Apr 18, 2026)

- [x] Overhaul `top_nav.html` — sticky nav, Product/Solutions/Pricing/Resources links, mobile drawer
- [x] Generate hyper-realistic dashboard hero image
- [x] Overhaul `landing_page.html` — real hero image, feature grid, how-it-works, pricing preview
- [x] Create `/product/` page — 6 feature sections showcasing Sprint 1-6 deliverables
- [x] Create `/solutions/` page — Energy, Cold Chain, Factory use cases
- [x] Create `/pricing/` page — 3 tiers + feature comparison table + FAQ accordion
- [x] Create `/about/` page — mission, story, contact
- [x] Build Wagtail templates for Resources hub (Blog index, Doc pages)
- [x] Overhaul `footer.html` — multi-column professional footer
- [x] Add URL routes for new pages
- [x] Run tests + visual verification

---

## Sprint 7C: Onboarding Polish + Architecture Refinements — ✅ COMPLETE (Apr 18, 2026)

- [x] Add RBAC checks to onboarding views
- [x] Redesign completion page with summary + quick action cards
- [x] Add Alpine.js conditional field visibility to automation form
- [x] Add `generate_preventive_tickets` to `CELERY_BEAT_SCHEDULE`
- [x] Run tests + visual verification
