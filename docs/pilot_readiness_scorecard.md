# Novena Pilot-Readiness Scorecard

## Current Audit State
Run this before each audit session:

```bash
~/.venvs/novena/bin/python manage.py pilot_readiness_audit simulate
~/.venvs/novena/bin/python manage.py pilot_readiness_audit keepalive --minutes 45 --interval-seconds 20
~/.venvs/novena/bin/python manage.py pilot_readiness_audit snapshot
```

Use `keepalive` for simulation audits only. Hardware replay should prove real gateway heartbeat, discovery, telemetry, alerting, and maintenance behavior without simulation refreshes.

Use this file as the living scorecard. Keep findings concrete: what the customer tried, what happened, why it matters, and the recommended fix.

Note: the journey scores below are from the pre-fix audit pass. Re-run the walkthrough with simulation keepalive before updating scores.

## Persona Scores

| Persona | Journey | Score 0-3 | Priority | Notes |
| --- | --- | ---: | --- | --- |
| Cold chain operator | Onboarding to first live dashboard | 2 | P1 pilot friction | Login and dashboard work, device readings are prominent, and the setup CTA is discoverable. However `/a/pilot-cold-room/onboarding/` redirects to the dashboard instead of the setup explanation, and the simulated gateway/device showed "offline" within minutes, so the first live-dashboard confidence is not pilot-ready yet. |
| Cold chain operator | High-temperature alert to maintenance ticket | 2 | P1 pilot friction | Alert acknowledgement worked, ticket was already linked, checklist/comment updates worked, and the contractor public link accepted a logged-out contractor comment. The alert row shows device, value, severity, status, and ticket link, but threshold and recommended next action are only clear after opening the ticket, not at the alert decision point. |
| Factory owner | Energy visibility and anomaly recovery | 2 | P1 pilot friction | Power meter and VFD are easy to find, recovery alert state is resolved, history/export page loads, and CSV export works. The CSV exports `Timestamp,Key,Value` without business labels/units, and the dashboard still reports gateway/devices offline after simulation, weakening confidence that the plant is currently healthy. |
| Factory owner | Gateway logs/RPC confidence | 2 | P1 pilot friction | Gateway logs and RPC history pages load, and the log message is understandable. The gateway detail page still uses terms like "RPC", "Trigger Port Scan", "Restart All Connectors", MQTT credentials, and raw params/status, so an owner can use it with guidance but it still feels closer to an engineer console than an owner view. |
| Facilities manager | Multi-site fleet scan | 2 | P1 pilot friction | `/a/pilot-facilities/` and site/device lists show two sites, devices, gateway counts, alerts, and work items. The scan is useful, but all simulated devices/gateways read offline shortly after seeding, which makes the fleet state feel unreliable for a manager checking live operations. |
| Facilities manager | Preventive maintenance and contractor workflow | 2 | P1 pilot friction | Monthly chiller PM schedule exists; ticket status, checklist, internal comment, public contractor link, and contractor comment all worked. The contractor portal is functional and narrow around the ticket, but it also renders full public marketing navigation including broken `Blog` links to `/None`, which hurts the "safe limited external workflow" impression. |

## Findings Backlog

### P0 Blockers
- None recorded yet.

### P1 Pilot Friction
- Addressed: Device-specific alert rules were matching other devices at the same site when the rule also stored a site reference. This could make a power-meter threshold fire on a chiller that happened to emit the same telemetry key. Fixed matching so site-wide rules only apply when no specific device is set.
- Addressed: Added simulation-only `pilot_readiness_audit keepalive` so manual simulated audits remain live without changing production freshness thresholds or masking hardware replay issues.
- Addressed: Existing-team `/onboarding/` now sends customers to the setup flow instead of silently returning to the dashboard.
- Addressed: Alert rows now show metric labels/units, threshold wording, linked-ticket next action, and status context directly in the list.
- Addressed: Factory telemetry CSV export now includes `Timestamp,Metric,Key,Value,Unit`.
- Addressed: Gateway command UI uses operator-facing "Command History" / "Remote Command" wording instead of visible software-centric RPC copy.
- Addressed: Contractor public ticket pages suppress broad marketing navigation, and global Blog links are hidden when no CMS blog URL exists.

### P2 Polish
- The local audit pages render the Django Debug Toolbar in the customer session. This is expected in development, but make sure it is disabled for any pilot/demo environment.
- Several customer-facing phrases are still generic or technical, for example "Hardware Found", "Provision Now", "Telemetry Key", and "Compliance Reporting". Plain operational wording would improve confidence for non-technical SMEs.

### P3 Later
- None recorded yet.

## Evidence Checklist
- Screenshot: onboarding start and gateway claim.
- Screenshot: gateway wait/discovery state.
- Screenshot: first live device dashboard for each persona.
- Screenshot: alert detail/list row showing device, value, threshold, and action.
- Screenshot: maintenance ticket with checklist and shared contractor link.
- CSV export sample for factory telemetry.
- Hardware replay notes for each serial.

## Hardware Replay Results

| Replay Serial | Persona | Claim | Discovery | First Telemetry | Alert | Maintenance | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `NOV-AUDIT-COLD-HW` | Cold chain operator | TBD | TBD | TBD | TBD | TBD |  |
| `NOV-AUDIT-FACTORY-HW` | Factory owner | TBD | TBD | TBD | TBD | TBD |  |
| `NOV-AUDIT-FACILITY-HW` | Facilities manager | TBD | TBD | TBD | TBD | TBD |  |
