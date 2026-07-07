# Novena Pilot-Readiness Customer Simulation Runbook

## Purpose
This runbook tests Novena as a first paid pilot customer would experience it. The goal is not to prove that tables and forms exist; it is to prove that a non-technical SME operator can go from gateway setup to useful operational action without needing an engineer beside them.

Use three personas:
- Cold chain operator: spoilage prevention, compliance confidence, fast alert-to-action.
- Factory owner: energy visibility, power anomaly handling, gateway/device confidence.
- Facilities manager: multi-site visibility, preventive maintenance, contractor coordination.

## Setup
Start the local stack, then prepare audit tenants and replay inventory:

```bash
~/.venvs/novena/bin/python manage.py pilot_readiness_audit prepare
```

The command creates:
- Login: `pilot.audit@novena.local`
- Password: `PilotReady123!`
- Teams: `pilot-cold-room`, `pilot-factory-energy`, `pilot-facilities`
- Simulation gateway serials and hardware replay serials, each with printed claim codes.

Generate the simulated customer states:

```bash
~/.venvs/novena/bin/python manage.py pilot_readiness_audit simulate
~/.venvs/novena/bin/python manage.py pilot_readiness_audit keepalive --minutes 45 --interval-seconds 20
~/.venvs/novena/bin/python manage.py pilot_readiness_audit snapshot
```

`simulate` writes MQTT-shaped telemetry into the app and creates realistic discovery, alert, dashboard, maintenance, and contractor-link states. Use `--publish-mqtt` when the local broker and consumer are running and you also want actual MQTT traffic.

`keepalive` is only for simulated pilot walkthroughs. It refreshes the audit simulation gateway heartbeats and telemetry so dashboards remain live during a manual customer audit. Do not use it for hardware replay; physical gateways should prove their own heartbeat, discovery, telemetry, alerting, and recovery behavior.

## Scoring
Score each journey from `0` to `3`.

| Score | Meaning |
| --- | --- |
| 0 | Broken: customer cannot finish the task. |
| 1 | Works only with technical help or admin intervention. |
| 2 | Works, but friction, unclear copy, or confidence gaps remain. |
| 3 | Customer-ready for a first paid pilot. |

Mark priority:
- `P0 blocker`: prevents pilot completion or risks wrong operational action.
- `P1 pilot friction`: customer can finish, but confidence or simplicity is not good enough.
- `P2 polish`: visible refinement, mobile, wording, spacing, loading, or empty-state improvement.
- `P3 later`: valuable, but not needed for first pilot.

## Journey 1: Cold Chain Operator
Team URL: `/a/pilot-cold-room/`

Customer job: “I need to know before food stock is at risk.”

Checklist:
- Open onboarding and confirm the flow explains site, gateway, device, and alert steps in plain language.
- Claim the hardware replay gateway using the printed `NOV-AUDIT-COLD-HW` serial and claim code when testing with real hardware.
- In simulation, open the site and gateway pages and verify gateway state reads as live with last-seen context.
- Confirm discovered cold room sensor maps to the correct template without technical guessing.
- Open the device dashboard and verify temperature, humidity, door, and compressor readings are prominent.
- Confirm the high-temperature alert is understandable: affected device, current value, threshold, severity, and next action.
- Acknowledge the alert and escalate/create a maintenance ticket.
- Share the ticket with a contractor and open the public link in a logged-out/private session.
- Score whether the customer knows what to do next at every step.

Expected pilot-ready outcome:
- Live dashboard is obvious.
- High temperature is treated as a business incident, not just a raw number.
- Contractor can update checklist/comments without receiving full app access.

## Journey 2: Factory Owner
Team URL: `/a/pilot-factory-energy/`

Customer job: “Show me where energy is going and tell me when something is abnormal.”

Checklist:
- Verify site, gateway, power meter, and VFD are easy to find from navigation.
- Confirm the power dashboard prioritizes active power, voltage, current, frequency, and energy.
- Check that the power-spike incident is visible in alert history and resolves after recovery telemetry.
- Export telemetry CSV and confirm labels/units are understandable to a business user.
- Inspect gateway logs and RPC history; score whether the copy is understandable without knowing MQTT or Modbus.
- Attempt a device command only if the UI makes the target, risk, and status clear.
- Score whether this feels like “energy monitoring for owners,” not an engineer console.

Expected pilot-ready outcome:
- Owner can answer “what changed?” and “is it back to normal?” quickly.
- Gateway/device technical details do not obscure business interpretation.

## Journey 3: Facilities Manager
Team URL: `/a/pilot-facilities/`

Customer job: “I manage multiple sites and need work to move from dashboard to technician.”

Checklist:
- Confirm team home/fleet view makes multiple sites scannable.
- Verify site/device/gateway lists have clear statuses and last-seen context.
- Open the chiller dashboard and confirm live status and abnormal temperature state are clear.
- Confirm preventive maintenance schedule exists and is understandable.
- Create or inspect a maintenance ticket, move it through statuses, complete checklist items, add a comment, and verify audit trail.
- Invite/view a read-only member or validate viewer permissions if available.
- Open a contractor shared link and verify the external workflow is narrow, clear, and revocable.
- Score mobile/tablet usability for dashboard and ticket workflow.

Expected pilot-ready outcome:
- Facilities manager can coordinate work without losing context between site, device, alert, and ticket.
- External contractor access feels safe and limited.

## Hardware Replay
After simulation, replay the exact same journey with physical hardware.

Use the hardware replay serials printed by `prepare`:
- `NOV-AUDIT-COLD-HW`
- `NOV-AUDIT-FACTORY-HW`
- `NOV-AUDIT-FACILITY-HW`

Replay rules:
- Use the same persona, expected outcome, and scoring sheet.
- Record every difference between simulation and hardware.
- Treat mismatches as product findings, not hardware footnotes.
- Confirm gateway bootstrap, claim, online heartbeat, discovery, config push, first telemetry, alerts, maintenance ticket, and recovery.

## Done Criteria
The platform is pilot-ready when:
- Each persona scores at least `2` on every core journey and `3` on onboarding/live-dashboard confidence.
- No `P0 blocker` remains.
- All `P1 pilot friction` items have either a fix, a clear workaround, or a deliberate first-pilot support script.
- Hardware replay matches simulation for gateway claim, discovery, telemetry, alerting, and maintenance action.
