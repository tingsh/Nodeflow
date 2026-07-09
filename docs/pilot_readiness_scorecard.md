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

Note: the journey scores below are from the post-polish audit pass on July 7, 2026. Simulation keepalive was running; physical hardware replay was not performed.

## Persona Scores

| Persona | Journey | Score 0-3 | Priority | Notes |
| --- | --- | ---: | --- | --- |
| Cold chain operator | Onboarding to first live dashboard | 2 | P1 pilot friction | `/a/pilot-cold-room/onboarding/` now reaches the customer setup path instead of silently dumping the user into the dashboard, and the live dashboard clearly shows gateway heartbeat plus temperature, humidity, door, and compressor readings. It is still closer to "add infrastructure" than a plain-language walkthrough of site → gateway → device → alert, and stale "Hardware Found / Provision Now" notifications remain visible after the simulated hardware is already usable. |
| Cold chain operator | High-temperature alert to maintenance ticket | 2 | P1 pilot friction | Alert acknowledgement works with the browser CSRF flow, the linked ticket is easy to reach, status/checklist updates work, and the logged-out contractor portal accepts activity comments without full app access. The alert list still does not make threshold/next action as plain as the ticket detail, and the ticket copy still says "Telemetry Key: temperature", which reads like an engineer field rather than an operator instruction. |
| Factory owner | Energy visibility and anomaly recovery | 2 | P1 pilot friction | Site, gateway, power meter, and VFD are easy to find; power readings are prominent and the spike alert is shown as resolved after recovery telemetry. The CSV download still exports raw `Timestamp,Key,Value` rows from `/telemetry/api/export/...` without the expected Metric/Unit columns, so a business user still has to interpret keys like `active_power` and `output_frequency`. |
| Factory owner | Gateway logs/RPC confidence | 2 | P1 pilot friction | Gateway pages now use "Command History" and "Remote Command" instead of visible RPC wording, and logs/history pages load. The device command area still exposes Modbus/register-address concepts and an expert-mode warning, so the owner can understand status but the page still feels partly like an engineer console. |
| Facilities manager | Multi-site fleet scan | 3 | P2 polish | `/a/pilot-facilities/` and the site/device/gateway lists make the two-site portfolio scannable, with live device status, gateway heartbeat, alert count, work item count, and last-sample context visible during keepalive. Remaining issues are polish-level in this journey: development debug toolbar is visible locally, and the persistent "Hardware Found / Provision Now" notification can distract from the otherwise clear fleet view. |
| Facilities manager | Preventive maintenance and contractor workflow | 1 | P1 pilot friction | Monthly chiller PM schedule exists, ticket status changes work, checklist toggles work, and the logged-out contractor portal is now narrow and free of broad marketing nav. However, submitting an internal ticket comment returns HTTP 500 due to `maintenance_ticketcomment.team_id` being null, so the manager cannot reliably add an audit-trail note from the authenticated ticket page. |

## Findings Backlog

### P0 Blockers
- None recorded yet.

### P1 Pilot Friction
- Addressed in follow-up polish: Internal authenticated maintenance ticket comments now set `team_id` and accept attachments, so operator audit-trail notes can be saved from the authenticated ticket page.
- Addressed in follow-up polish: The streaming telemetry CSV exporter now returns `Timestamp,Metric,Key,Value,Unit` and uses template labels/units instead of raw-only keys.
- Addressed in follow-up polish: Discovery notifications now only show gateways with unresolved discovered devices; fully registered simulated hardware no longer keeps prompting setup. Notification copy now says "New Device Ready" / "Review Setup".
- Addressed: Device-specific alert rules were matching other devices at the same site when the rule also stored a site reference. This could make a power-meter threshold fire on a chiller that happened to emit the same telemetry key. Fixed matching so site-wide rules only apply when no specific device is set.
- Addressed: Added simulation-only `pilot_readiness_audit keepalive` so manual simulated audits remain live without changing production freshness thresholds or masking hardware replay issues.
- Addressed: Existing-team `/onboarding/` now sends customers to the setup flow instead of silently returning to the dashboard.
- Addressed: Alert rows now show metric labels/units, threshold wording, linked-ticket next action, and status context directly in the list.
- Addressed in follow-up polish: Factory telemetry CSV export now includes `Timestamp,Metric,Key,Value,Unit` on the customer-facing export route.
- Addressed: Gateway command UI uses operator-facing "Command History" / "Remote Command" wording instead of visible software-centric RPC copy.
- Addressed: Contractor public ticket pages suppress broad marketing navigation, and global Blog links are hidden when no CMS blog URL exists.

### P2 Polish
- The local audit pages render the Django Debug Toolbar in the customer session. This is expected in development, but make sure it is disabled for any pilot/demo environment.
- Addressed in follow-up polish: Reworded several technical phrases, including "Hardware Found", "Provision Now", "Telemetry Key", "Deep probe", and "Compliance Reporting", toward plainer operator-facing language.
- Public contractor pages no longer show the broad marketing navigation, but they still render the local Django Debug Toolbar in development.

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
