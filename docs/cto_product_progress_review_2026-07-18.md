# Novena Platform — CTO Product Progress Review

> **Date:** 18 July 2026  
> **Scope:** Current Novena Hub and Novena Gateway codebases, including the latest uncommitted Gateway hardening work  
> **Previous full-stack review:** [27 April 2026](archive/progress_reviews_2026_h1/progress_review_april_27.md)  
> **Launch execution plan:** [20-customer pilot checklist](20_customer_pilot_launch_checklist_2026-07-31.md)

## Executive Decision

Novena is no longer a simulated SaaS front end with an experimental edge component. It is a substantial full-stack industrial monitoring product with a differentiated managed-Gateway direction, working commissioning concepts, telemetry, dashboards, alerts, maintenance workflows, notifications, billing foundations, and a hardened Raspberry Pi CM4 edge runtime.

The recent Gateway work materially improves the product. It moves Novena Gateway from “Python protocol bridge” toward “supportable industrial appliance” through deployment-mode validation, TLS requirements, startup and connector health, last-known-good configuration rollback, offline buffering, diagnostics, hardware preflight, scoped privileged operations, secret redaction, and stronger OTA lifecycle handling.

The updated CTO decision is nevertheless:

> **HOLD the 20-customer handout. CONDITIONAL GO for a 3–5 customer technical canary only after the P0 items in this review are fixed, committed, tested, and replayed on real CM4 hardware.**

The reason is not lack of features. The remaining blockers sit directly on customer isolation, first-time Gateway activation, tenant scoping, firmware trust, and reproducible deployment. Those are exactly the risks that multiply when twenty external gateways are introduced at once.

## 1. Evidence and Confidence Rules

This review distinguishes four levels of confidence:

- **Built:** The behavior exists in source code.
- **Tested:** Automated or local workflow evidence exists.
- **Hardware-verified:** The current release has passed the real CM4 and field-device path.
- **Pilot-proven:** A non-developer customer has completed the journey at a real site with sustainable support effort.

“Built” is not treated as “pilot-proven.” In particular:

- The Gateway branch `codex/gateway-pilot-readiness` is pushed through commit `ab77ba6`.
- A further substantial Gateway hardening layer is still uncommitted: 18 modified tracked files plus new hardware, helper, redaction, documentation, configuration, and test assets.
- The Hub working tree also contains uncommitted production-readiness assets.
- The July pilot scorecard is based on simulation. The three current vertical CM4 replay rows remain `TBD`.
- A previous local Laptop 2 → CM4 → MQTT → Hub test is useful evidence, but it does not validate the current hardened build, production TLS/ACL design, or all three vertical journeys.

## 2. Current Maturity Scorecard

| Area | Assessment | Confidence | CTO score |
| --- | --- | --- | ---: |
| Hub feature completeness | Broad and commercially credible product surface | High from code; medium from current runtime evidence | 8.5/10 |
| Gateway committed branch | Good supervised-pilot software baseline | Medium-high | 7.0/10 |
| Gateway current working tree | Material appliance, security, and supportability improvements | Medium; latest layer uncommitted and not fully tested | 7.8/10 |
| Integrated evidence-backed readiness | Key end-to-end security and activation issues remain | Medium-high | 6.0/10 |
| Customer-pilot readiness | Suitable for internal replay after P0 fixes; not yet for 20 handouts | High | 5.5/10 |
| Commercial readiness | Offer, target vertical, and value proposition are clear; willingness to pay is unproven | Medium | 6.0/10 |

These scores are decision aids, not percentages of code completed. The lowest cross-system constraint governs the launch.

## 3. What Is Now Materially Built

### Novena Hub

The Hub is a credible multi-tenant industrial SaaS control plane:

- Team tenancy, invitations, RBAC, owner/manager/member/viewer behavior, and account/team closure.
- Site → Gateway → equipment hierarchy with inventory-backed Gateway claim, release, and reclaim.
- Random operational MQTT credentials stored hashed in Hub rather than using the sticker claim code as the permanent password.
- Solution-profile onboarding for energy, cold chain, and facilities/HVAC.
- Discovery reports, ranked template matching, Cloud-generated Modbus TCP/RTU configuration, and configuration acknowledgements.
- TimescaleDB telemetry, Redis/Celery buffering, WebSockets with polling fallback, CSV export, and site-local operational timezones.
- Adaptive equipment dashboards and multi-site operations views.
- Alert rules, cooldown, acknowledgement, resolution, escalation, email delivery audit, and approved WhatsApp trigger templates.
- Maintenance tickets, preventive schedules, checklists, comments, attachments, and limited contractor links.
- Unified customer device-command audit linked to underlying Gateway transport commands.
- Automations, AI chat/insights, Wagtail marketing content, and public signup.
- Stripe checkout/portal foundations and enforcement for Gateway, device, retention, and telemetry-interval limits.
- A pilot-audit simulator and customer-journey scorecard.

The product surface is now broad enough. The near-term work should reduce failure modes and support burden rather than add another major module.

### Novena Gateway — committed baseline

The pushed Gateway branch contains important production-minded behavior:

- MQTT TLS configuration, QoS 1, last-will status, reconnect backoff, bootstrap fallback, activation, and credential rotation.
- SQLite offline buffering and throttled replay with buffer-health attributes.
- Remote configuration with atomic writes, backups, last-known-good state, connector restart, and rollback on connector failure.
- Connectivity diagnostics for route, DNS, TCP, TLS, and broker reachability.
- Modbus device-health tracking, error classification, on-demand reads/writes, and normalized command results.
- OTA HTTPS checks, required SHA-256, payload structure checks, candidate configuration validation, atomic release switching, service health check, and rollback.
- Unprivileged service execution, standard `/etc`, `/var/lib`, and `/var/log` paths, and systemd watchdog notifications.

### Novena Gateway — latest working-tree hardening

The newest work strengthens the appliance model further:

- CM4/Waveshare hardware setup for USB host, SPI/CAN, RS-485 UART overlays, and RTC.
- Read-only hardware preflight covering boot configuration, ports/interfaces, disk, clock, groups, and helper availability.
- A narrow privileged helper for reboot, service restart, route metrics, CAN configuration, and OTA execution.
- Pilot/production TLS enforcement and placeholder rejection.
- Required-connector startup policy and `ready`, `degraded`, or `failed` startup status.
- Connector results, queue pressure, dropped-message count, and device-health diagnostics.
- Diagnostic-only network-watchdog behavior when privileged actions are unavailable.
- Secret redaction for config, RPC responses, attributes, acknowledgements, and remote logs.
- Configurable Modbus TCP target/port discovery across interfaces.
- SQLite time-to-live cutoff correction and an exact `pymodbus==3.8.0` compatibility pin.
- A customer-deployment readiness guide and 24–48 hour burn-in checklist.

This work improves serviceability and reduces the need to SSH into customer gateways. That is commercially important: the managed appliance and its support workflow are becoming part of Novena's moat.

## 4. What the Gateway Hardening Changes Strategically

The product should no longer be described as “SaaS plus a cheap Raspberry Pi.” The product unit is:

> **A managed Novena Gateway appliance + a verified equipment template + a vertical outcome pack + remote support and lifecycle management.**

That changes several business assumptions:

1. Gateway assurance has value and cost. Provisioning, burn-in, diagnostics, replacement stock, and lifecycle support should not be hidden inside an unrealistically cheap SaaS plan.
2. “Plug-and-play” must mean no software engineering after safe physical installation—not that an owner should wire live panels.
3. Template trust is a product asset. A register map is not verified because it exists in JSON; it is verified when the exact model, scaling, byte order, valid ranges, and field output are evidenced.
4. Remote diagnostics reduce service cost only if Hub stores and presents them. New Gateway attributes that Hub ignores do not yet create customer or support value.
5. AI remains downstream. Reliable identity, telemetry, freshness, alerts, and action must be proven first.

## 5. P0 Blockers Before Any External Canary

### P0-1 — Gateway activation can be lost when the unit is offline during claim

Hub provisions a new operational MQTT password and immediately publishes the activation message. The activation publish is QoS 1 but not retained, and Hub does not persist the plaintext credential for safe retry. The customer journey tells the user to claim first and then power/connect the Gateway. When the Gateway later publishes `bootstrap/hello`, Hub records that it was seen but does not resend activation.

**Impact:** The advertised onboarding order can leave a correctly claimed Gateway permanently waiting for credentials.

**Required resolution:** Introduce an explicit activation state machine with a one-time encrypted/escrowed activation secret or equivalent secure broker mechanism, retry activation on bootstrap hello, require a Gateway acknowledgement, expire the activation payload, and test offline-at-claim plus retry behavior.

### P0-2 — One Gateway can impersonate another on shared inbound MQTT topics

Telemetry, logs, attributes, and RPC responses use shared inbound topics. Hub resolves the Gateway from the payload `serial_number`. The shared Mosquitto `gateway` role permits every valid Gateway to publish to those topics.

**Impact:** A compromised or defective Gateway can submit telemetry, health data, logs, or request identifiers under another customer's serial number.

**Required resolution:** Move inbound traffic to serial-scoped topics, grant each client only its own publish namespace, derive the Gateway identity from the topic/authenticated client context, and reject payload/topic mismatches. Add two-tenant broker-level tests.

### P0-3 — HTMX quick-add is not tenant-scoped

The quick-add route accepts `gateway_id` and `site_id`, loads a Gateway without `team=request.team`, can delete an existing device by foreign Gateway/port, creates a request-team device linked to caller-supplied foreign objects, and then pushes configuration to that Gateway.

**Impact:** Cross-customer device mutation and configuration push are possible through crafted requests.

**Required resolution:** Scope every Site, Gateway, Device, and template lookup to the active team, validate relationships before mutation, use transactions, and add explicit cross-tenant negative tests.

### P0-4 — OTA does not yet have an adequate trust boundary

The Gateway requires a SHA-256, but the expected checksum comes in the same RPC as the download URL. There is no vendor-signed manifest or pinned signing key. The caller-provided version reaches root-run release paths and generated files without a strict version grammar. The current path also permits a caller-controlled insecure-download override and extracts an archive as root.

**Impact:** A compromised control path could install attacker-controlled code or exploit path/archive handling.

**Required resolution:** For the canary, either disable OTA entirely or add strict version validation, canonical paths, archive traversal/link checks, no caller-controlled HTTPS bypass, and vendor signature verification with a trust key burned into the appliance. Config-file permissions must also be restricted because the current installer does not explicitly protect MQTT/claim secrets from other local users.

### P0-5 — The release is not reproducible from a clean checkout

The latest Gateway appliance work and Hub deployment kit are uncommitted. The production Mosquitto example contains no roles/clients while Hub provisioning assumes a pre-existing `gateway` role. Docker Compose validation has not been run in this environment.

**Impact:** The development workstation contains more capability than the source-controlled release, and a clean deployment may not reproduce the tested broker behavior.

**Required resolution:** Split and commit the current work into reviewed changes, align the production broker seed with provisioning/bootstrap behavior, build release artifacts from a clean checkout, record checksums, and run the same installation procedure used for the canary gateways.

## 6. P1 Reliability and Product Gaps

### Hub and Gateway contract

- Hub does not yet persist or surface the new `startup_status`, connector-start results, device-health details, data-queue pressure, hardware preflight, or privilege-preflight evidence in a coherent support view.
- Config/RPC publishing creates pending database records but does not wait for broker acknowledgement or implement a durable retry/outbox.
- Onboarding catches some scan/config-push exceptions and can move forward without proving command delivery.
- Remote config has no explicit monotonic version or lock, so concurrent/stale updates can race.

### Telemetry integrity

- Hub removes the full Redis telemetry list before parsing and database write. A worker crash after deletion can lose the batch.
- When device identity is missing or invalid, Hub falls back to the first device on a Gateway. In a multi-device Gateway this can assign measurements to the wrong asset.
- Gateway replay currently treats local Paho publish acceptance as success rather than waiting for broker PUBACK. True end-to-end at-least-once delivery is therefore not yet proven.

For the pilot, require Cloud-assigned `device_id`, reject unresolved identity, use a recoverable queue/claim pattern, and test outage/replay with duplicate detection.

### Field-appliance behavior

- CM4/Waveshare overlay values, RS-485 direction behavior, CAN oscillator/interrupt, RTC, USB, 4G, and multi-WAN still need exact-board validation.
- The network watchdog passes interface names to NetworkManager operations, while real connection-profile names can differ.
- CAN overlay setup does not prove `can0` is configured and raised at boot; preflight currently checks configuration presence more than live CAN operation.
- Discovery can scan a `/24` on every active interface. Pilot discovery should be limited to approved plant interfaces/targets.
- Systemd service sandboxing can be strengthened further.

### External integrations and billing

- Stripe webhook validation is disabled in base settings and not overridden in production settings. Live Stripe behavior and dunning are not proven.
- A custom Stripe webhook path can return success even when event processing fails.
- Incoming WhatsApp maintenance messages do not validate Meta's request signature and use permissive phone suffix matching before mutating tickets.
- Real SES sending and an approved WhatsApp trigger template have been locally demonstrated, but production delivery/bounce/complaint handling and all message types remain unproven.

These do not all block a free supervised technical canary if billing and inbound WhatsApp mutation are disabled. They do block treating the system as a self-serve paid production service.

## 7. Current Validation Results

### Gateway

- `git diff --check`: passed.
- Python compile check across Gateway source/tests: passed.
- Shell syntax for installer, upgrade, hardware setup, and helper: passed in the audit.
- `unittest discover`: 67 modules/tests attempted; 64 tests passed and 3 modules failed to import because the audit environment lacks `sdnotify`, `pymodbus`, and `simplejson`.
- The new hardening test module did not execute because of the missing `sdnotify` dependency.
- No repository CI workflow was found.
- No current CM4/Waveshare replay evidence was found for the uncommitted hardened build.

### Hub

- `manage.py check`: completed with warnings for disabled dj-stripe webhook validation, deprecated allauth settings, missing database Stripe keys, and the deprecated `google.generativeai` package.
- `makemigrations --check --dry-run`: no model changes detected.
- A current focused run covering Gateway commissioning, commands, telemetry, subscription enforcement, production readiness, and public MQTT copy reported 40 passed and 2 failed. Both failures use fixed 13 July samples and query the latest 24 hours on 18 July, so they are date-brittle tests rather than observed product regressions; replace their fixed times with `timezone.now()`-relative data.
- Hub tests can accidentally target the shared PostgreSQL environment unless `USING_TEST_DB=True` is set because the settings switch checks for the exact `test` argument. Standardize the pytest configuration before running the full suite.
- The project log records focused prior passes across Gateway commissioning/telemetry, devices/commands, alerts/email, web, and readiness checks.
- A current full Hub suite was not run during this review; do not interpret historic focused passes as a current clean full suite.

## 8. Updated Product Readiness by Customer Journey

| Journey | Capability | Current verdict |
| --- | --- | --- |
| Signup and team setup | Built and polished | Ready for supervised use |
| Claim Gateway | Inventory, limits, credentials, and reclaim built | **Blocked by offline activation race** |
| Secure Gateway identity | Credentials and broker ACL concepts built | **Blocked by shared inbound spoofing risk** |
| Discover equipment | Stronger Edge scanning and Hub matching built | Assisted only; restrict scan scope and verify exact equipment |
| Push configuration | Ack, status, rollback, and LKG built | Promising; durable delivery/versioning still needed |
| First telemetry | Working pipeline and dashboards built | Require exact device identity; remove first-device fallback |
| Alert and action | Mature alert/ticket flow | Ready after telemetry identity; inbound WhatsApp mutation must be secured or disabled |
| Offline recovery | Edge buffering/replay built | Needs PUBACK-backed real-hardware evidence |
| OTA lifecycle | Feature-rich implementation | Disable or harden trust boundary before external pilot |
| Paid conversion | Plans and Stripe foundations built | Not live-ready until webhook validation and live flow pass |

## 9. Revised Launch Gates

### Gate A — Code and security closure

- [ ] Fix and test the activation retry/acknowledgement flow.
- [ ] Implement serial-scoped inbound MQTT identity and two-tenant isolation tests.
- [ ] Fix all tenant scoping in quick-add/device creation paths.
- [ ] Disable OTA for canary or complete signed, validated OTA hardening.
- [ ] Restrict Gateway config/certificate permissions.
- [ ] Commit Hub and Gateway release assets and build from a clean checkout.

### Gate B — Integrated reliability

- [ ] Require exact Cloud device identity; remove ambiguous first-device assignment.
- [ ] Make Hub telemetry queue processing recoverable.
- [ ] Wait for publish acknowledgement and add durable retry for control messages.
- [ ] Persist and present new Gateway health/preflight attributes in Hub support tooling.
- [ ] Run all Hub/Gateway focused suites with the declared dependencies installed.

### Gate C — Current hardware replay

- [ ] Factory/energy CM4 replay passes claim, activation, discovery, config, telemetry, alert, recovery, outage replay, reboot, and safe-update/disabled-update behavior.
- [ ] Cold-chain replay passes the same path with exact sensor and threshold validation.
- [ ] Facilities/HVAC replay passes the same path with exact equipment and maintenance workflow validation.
- [ ] Complete 24–48 hour burn-in on each representative hardware configuration.

### Gate D — Five-customer canary

- [ ] Five qualified sites only; no unsupported equipment.
- [ ] One primary monitored asset per site.
- [ ] No writable control unless separately safety-reviewed.
- [ ] At least four reach first trustworthy data.
- [ ] No P0, cross-tenant event, false healthy state, or unrecoverable data loss.
- [ ] Support burden and replacement process are sustainable.

Only after all four gates pass should the remaining fifteen kits be released.

## 10. Priorities

### Next 72 hours

1. Freeze feature work and convert the P0 list into tracked fixes with owners.
2. Resolve MQTT identity and activation design first; they affect the foundational commissioning promise.
3. Fix the cross-tenant quick-add path and add regression tests.
4. Decide whether OTA is disabled for the pilot or fully hardened now.
5. Commit the current Gateway appliance work in reviewable units and restore a dependency-complete test environment.

### Following 7 days

1. Close the telemetry identity/queue and control-message delivery gaps.
2. Map the new Gateway runtime/preflight data into a support-facing Hub view.
3. Produce a clean Gateway release artifact and CM4 image.
4. Complete three current physical vertical replays.
5. Run the five-customer canary only when the replay evidence is green.

### Following 30–90 days

1. Convert successful canaries into paid design partners and measure support cost.
2. Select the strongest initial wedge—energy remains the leading hypothesis—using real conversion and outcome data.
3. Expand only the exact-device template library required by qualified pipeline.
4. Establish an installer/controls partner model before scaling site count.
5. Complete Stripe, signed OTA, broker provisioning, observability, backup/restore, and incident-response readiness before self-serve paid launch.

## CTO Conclusion

The recent Gateway hardening is the right work. It strengthens the part of Novena that is hardest for generic SaaS competitors to reproduce: a remotely supportable edge appliance that connects industrial equipment to a simple SME operations product.

The hardening also exposes the correct next stage of the company. Novena does not need more breadth before the pilot. It needs integrity across identity, activation, telemetry, configuration, and field recovery. Closing those gaps and proving five sites will create more enterprise value than launching twenty boxes on a deadline.

The business remains a **conditional go**. The technology is credible; the repeatability and trust boundary must now be proven.
