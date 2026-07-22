# Novena Platform: 20-Customer Pilot Launch Checklist

**Target date:** Friday, 31 July 2026  
**Cohort:** 20 prospective SME customers  
**Product promise being tested:** A business owner can connect one supported asset, see useful operational information, receive an understandable alert, and know what to do next without software engineering or custom development.

This is a product-pilot checklist, not a general production-readiness checklist. It concentrates on the gateway kit, the customer journey, supported equipment, useful vertical outcomes, field installation, support, and learning whether customers will pay.

> **CTO hold gate — 18 July review:** The current code audit found launch-blocking issues in Gateway activation retry, inbound MQTT identity, HTMX tenant scoping, OTA trust, and reproducible release assets. Do not hand a kit to an external customer until Gate A in the [current CTO product review](cto_product_progress_review_2026-07-18.md#gate-a--code-and-security-closure) is complete. The five-customer canary and wider twenty-customer rollout are conditional on that evidence, not fixed calendar commitments.

## 1. Launch Definition and Ground Rules

### What “launched” means on 31 July

A customer counts as launched only when all of the following are true:

- [ ] The customer and site have passed the qualification checklist.
- [ ] One primary asset and business outcome are written down.
- [ ] The exact equipment make, model, protocol, and connection method are known.
- [ ] The equipment is supported by a field-verified template or a deliberately approved assisted setup.
- [ ] The customer has signed the pilot and gateway-loan terms.
- [ ] A customer account, site, gateway, owner, and support contact have been prepared.
- [ ] The assigned gateway kit has passed its bench and burn-in tests.
- [ ] An installation appointment and a responsible site contact are confirmed.
- [ ] The customer has received the kit, quick-start material, and support instructions.

Physical installation can occur in scheduled waves after handover, but a box without the items above does not count as a launched customer.

### Rules that protect the product promise

- [ ] **Freeze the pilot scope by 20 July.** One gateway, one site, and one primary asset per customer. Add a second asset only when it is the same supported model and adds no new engineering work.
- [ ] **Approve a no-custom-code rule.** The three vertical experiences may change onboarding copy, dashboards, alert presets, reports, and maintenance defaults; they must not become separate product forks.
- [ ] **Define plug-and-play honestly.** It means no SSH, JSON editing, register programming, or software engineer after safe physical installation. It does not mean an untrained business owner should wire live industrial equipment.
- [ ] **Use qualified installation help where needed.** Live electrical panels, control panels, RS-485 wiring, and regulated environments are handled by a qualified electrician or controls technician.
- [ ] **Defer unsupported equipment.** Do not promise that a generic template will work on an unknown asset.
- [ ] **Defer AI as a launch dependency.** The pilot succeeds on trustworthy monitoring, alerts, and actions. AI can be added after the underlying data and customer workflow are proven.

### Recommended pilot offer for founder approval

- [ ] Approve one standard 60-day managed design-partner pilot for all 20 customers.
- [ ] Loan the Novena Gateway rather than transferring ownership during the trial.
- [ ] Charge a commitment fee or refundable equipment deposit; credit a commitment fee toward the first paid subscription if the customer converts.
- [ ] State that extra sensors, electrical work, and third-party installation are outside the standard gateway trial and charged separately.
- [ ] Include one remote onboarding session and a defined level of pilot support.
- [ ] Include a trial end date, gateway return process, feedback expectation, and subscription conversion decision date.
- [ ] Require founder approval for any exception so sales experts cannot accidentally sell custom engineering.

## 2. Owners, Evidence, and Priority

Assign one person to every role by 20 July:

- [ ] **Launch owner:** Makes the final go/hold decision.
- [ ] **Product/Hub owner:** Owns onboarding, dashboards, alerts, reports, and customer-facing copy.
- [ ] **Gateway owner:** Owns the CM4 image, configuration, provisioning, logs, buffering, and replacement process.
- [ ] **Field owner:** Owns site surveys, safe installation requirements, cables, adapters, and installers.
- [ ] **Vertical sales owners:** One each for energy, cold chain, and facilities/hospitality.
- [ ] **Support owner:** Owns the support channel, issue triage, customer communication, and daily health review.

Priority definitions:

- **P0 — launch blocker:** The customer cannot complete the core journey, data can be wrong or assigned to the wrong customer, an unsafe action is possible, or the platform gives false confidence.
- **P1 — pilot friction:** The journey works only with avoidable help or confusing workarounds.
- **P2 — polish:** The journey works, but wording, layout, mobile behavior, or presentation reduces confidence.

An item is checked only when evidence exists: a signed form, site photo, serial number, screenshot, test record, video, or linked issue. “Someone said it works” is not evidence.

## 3. Customer and Site Qualification — Complete for All 20

Quality of fit is more important than forcing an equal vertical split. Aim for a balanced learning cohort of approximately 7 energy, 7 cold-chain, and 6 facilities/hospitality customers, but replace weak-fit prospects with qualified ones.

For every customer:

- [ ] Identify the decision-maker and the person who will use Novena each week.
- [ ] Record one measurable problem: energy visibility, temperature excursion, equipment downtime, multi-site visibility, or maintenance coordination.
- [ ] Record the current method: manual logbook, utility bill, standalone controller, spreadsheet, BMS, or no monitoring.
- [ ] Record the baseline burden: hours spent, incidents per month, avoidable cost, product loss, or response delay.
- [ ] Photograph the target equipment, nameplate, controller, communication terminals, and installation location.
- [ ] Record manufacturer, exact model, firmware if visible, protocol, port, unit address, baud rate, parity, IP address, and available registers/documents where applicable.
- [ ] Confirm the asset can be monitored without interfering with existing controls.
- [ ] Confirm power, Ethernet/Wi-Fi/cellular availability, signal quality, mounting space, cable length, and enclosure needs.
- [ ] Confirm whether the customer network requires a static IP, allowlist, proxy, VLAN, captive portal, or IT approval.
- [ ] Identify who is authorized to open panels or attach communication wiring.
- [ ] Confirm the site date, access hours, safety induction, permit, and named site contact.
- [ ] Confirm the exact template and vertical outcome pack that will be used.
- [ ] Mark the site **Supported**, **Assisted**, or **Deferred**.

Customer acceptance gate:

- [ ] **Supported:** Exact equipment and connection have passed bench or field verification. Eligible for self-guided onboarding after physical installation.
- [ ] **Assisted:** Equipment documentation is credible and the setup has a controlled installation plan, but the first field connection needs Novena supervision. Eligible only with a named technical owner.
- [ ] **Deferred:** Equipment, network, access, or safety details are unknown. Do not release a kit until resolved.

## 4. Gateway Fleet and Physical Kit — Prepare 23 Units

Prepare 20 customer kits plus 3 ready-to-dispatch spares. A spare is useful only when it is provisioned, tested, and packed—not when it is a loose CM4 on a shelf.

### Standard hardware

- [ ] Lock one pilot bill of materials and record part/revision numbers.
- [ ] Secure 23 Raspberry Pi CM4 gateway units with the same supported hardware revision.
- [ ] Secure 23 approved power supplies and country-correct plugs.
- [ ] Secure suitable enclosures, mounting hardware, labels, and tamper-evident seals.
- [ ] Prepare Ethernet cables and only the site-approved RS-485/BACnet/USB adapters and termination accessories.
- [ ] Prepare vertical accessory packs based on the qualified site—not a bag of generic parts.
- [ ] Label each gateway and box with serial number, kit number, support QR code, and return contact.
- [ ] Maintain a gateway inventory showing customer, serial, claim lifecycle, hardware revision, image version, accessories, handover date, and return status.

### Gateway image and configuration

- [ ] Freeze and label one Gateway release candidate by 23 July.
- [ ] Create a reproducible CM4 image/install procedure from that release.
- [ ] Confirm runtime state and credentials are outside the source tree.
- [ ] Confirm every gateway has a unique serial and bootstrap/claim identity.
- [ ] Confirm customer MQTT credentials are generated through the normal claim/provisioning flow rather than copied between units.
- [ ] Confirm the gateway can receive cloud configuration without requiring local JSON editing.
- [ ] Confirm failed configuration rolls back to the last known good configuration.
- [ ] Confirm telemetry buffers during an internet outage and replays without silently dropping a partial batch.
- [ ] Confirm power loss and restart do not require a technician to repair state.
- [ ] Confirm remote diagnostics expose enough information for support without exposing secrets to the customer.
- [ ] Confirm the Gateway config and certificate files are readable only by the required service/root accounts.
- [ ] Confirm pilot/production MQTT uses TLS and no customer can publish under another Gateway's identity.
- [ ] Confirm a Gateway that is offline during claim receives activation after its first bootstrap hello and sends an acknowledgement.
- [ ] Confirm `startup_status` is `ready`, or that a specific `degraded` state has been reviewed and accepted before handover.
- [ ] Confirm hardware and privilege preflight results are captured for the physical unit.
- [ ] Record the exact release, checksum, and build date installed on every unit.

### Per-unit acceptance test

Complete and attach a test record for every one of the 23 units:

- [ ] Visual inspection and serial/label match.
- [ ] Fresh boot and service auto-start.
- [ ] Ethernet and approved secondary network path connect.
- [ ] Gateway claim/provisioning works with a disposable test tenant.
- [ ] Heartbeat and clear online/last-seen status appear in Hub.
- [ ] Representative field protocol connects.
- [ ] First telemetry reaches the correct device and customer tenant.
- [ ] Alert triggers and notification is accepted by the configured provider.
- [ ] Network is disconnected; events buffer locally.
- [ ] Network is restored; buffered events replay once and in the correct order.
- [ ] Gateway is power-cycled; configuration and service recover automatically.
- [ ] Hardware preflight reports the expected CM4/Waveshare overlays, live ports/interfaces, synchronized clock, disk headroom, service groups, and scoped helper.
- [ ] Diagnostics and logs redact claim codes, MQTT passwords, tokens, private keys, and authorization values.
- [ ] Required connector failure produces a clear failed/degraded state and rolls configuration back to last known good.
- [ ] Queue pressure and dropped-message counters remain within the approved limit; unexplained dropped messages are zero.
- [ ] OTA is disabled for the pilot or passes the approved signed-manifest, strict-version, safe-archive, rollback, and trust-key test.
- [ ] Gateway is released/reset using the approved procedure and can be assigned to its final customer.
- [ ] Run a continuous 24-hour minimum burn-in with no unexplained service stop, storage growth, clock issue, or telemetry gap.
- [ ] Pack only after the bench result is signed by a second person.

## 5. Hub Product Experience — Minimum Polished Journey

The Hub must make the operational outcome clearer than the underlying protocol. Technical terms can exist inside a deliberately opened expert area, but not in the normal owner journey.

### Common horizontal journey

- [ ] A new customer can accept an invitation, create a password, and reach the correct team.
- [ ] The onboarding flow explains **site → gateway → equipment → alert** in plain language.
- [ ] The selected solution profile persists and never defaults a customer into the wrong vertical.
- [ ] Gateway claim clearly shows what was completed and what happens next.
- [ ] Discovery suggests only compatible templates and explains uncertain matches.
- [ ] Customers cannot select an unverified template as though it were proven.
- [ ] Configuration status distinguishes sent, accepted, applied, failed, and rolled back in customer-safe wording.
- [ ] First data is celebrated with an obvious “live” outcome dashboard and a trustworthy last-updated time.
- [ ] “Gateway online, equipment not reporting” is distinct from “gateway offline.”
- [ ] Alerts show the affected equipment, current value, threshold, time, severity, and recommended next action.
- [ ] Email and approved WhatsApp alert delivery are tested with real pilot recipients.
- [ ] Alert acknowledgement, maintenance ticket creation, comments, checklist, and contractor link work end to end.
- [ ] CSV exports use business labels, timestamps, and units rather than raw keys alone.
- [ ] Owner, manager, viewer, and contractor permissions are understandable and isolated by customer.
- [ ] Core pages are usable on the phone/tablet that the trial customers actually carry.
- [ ] Empty, stale, error, and disconnected states tell the customer what to do next.
- [ ] Normal owner screens do not require MQTT, Modbus, register address, RPC, telemetry key, JSON, or SSH knowledge.
- [ ] A visible Help/Support route contains the pilot contact and kit serial.

### Vertical outcome packs

These are configurations of one horizontal product, not separate products.

#### Energy monitoring

- [ ] Dashboard prioritizes live demand, energy use, abnormal demand, and trend—not a wall of electrical registers.
- [ ] Units and scaling are verified against a reference meter or simulator plus one real device.
- [ ] High-demand alert preset has an understandable threshold and next action.
- [ ] Customer can answer: “What is using energy, what changed, and did it recover?”
- [ ] Weekly summary provides at least energy use, peak demand, abnormal event count, and data coverage. Do not call it cost savings unless a tariff and comparison method are configured.

#### Cold chain

- [ ] Dashboard prioritizes temperature, door state, humidity where relevant, compressor state, and last update.
- [ ] Sensor accuracy/range and placement instructions are documented.
- [ ] Excursion threshold and delay prevent nuisance alerts while remaining suitable for the customer's operating requirement.
- [ ] Customer can answer: “Is stock at risk, for how long, and who responded?”
- [ ] Excursion history contains start, peak, duration, acknowledgement, and action. Do not claim regulatory compliance unless the complete evidence chain is actually supported.

#### Facilities and hospitality

- [ ] Portfolio view makes site, gateway, equipment, open alert, and work status easy to scan.
- [ ] HVAC/chiller/pump dashboard prioritizes operating state, temperature, runtime, abnormal state, and last update.
- [ ] Preventive maintenance preset, ticket workflow, and narrow contractor access are tested.
- [ ] Customer can answer: “Which site needs attention, what is wrong, and who owns the next action?”
- [ ] Weekly summary provides exceptions, downtime/data gaps, alerts, and open/completed work.

### Template trust gate

For each template used by the 20 customers:

- [ ] Exact manufacturer and model are recorded.
- [ ] Register map/protocol source and document revision are linked.
- [ ] Data type, byte/word order, scaling, unit, valid range, polling behavior, and writable status are reviewed.
- [ ] Bench or field evidence is attached.
- [ ] `Verified` means tested against the exact device or an explicitly compatible model—not merely reviewed or AI-generated.
- [ ] Any writable command is disabled for this pilot unless separately risk-reviewed and intentionally required.
- [ ] A rollback or template-disable path exists if field values are implausible.

## 6. Three Mandatory End-to-End Hardware Replays

The existing simulator journeys are useful, but they do not replace field evidence. Complete one replay per vertical and update `docs/pilot_readiness_scorecard.md`.

For `NOV-AUDIT-FACTORY-HW`, `NOV-AUDIT-COLD-HW`, and `NOV-AUDIT-FACILITY-HW`:

- [ ] Claim the real CM4 through the customer flow.
- [ ] Confirm heartbeat and last-seen state.
- [ ] Discover or deliberately select the representative equipment.
- [ ] Match the correct verified template without technical guessing.
- [ ] Push and acknowledge configuration.
- [ ] Show first trustworthy telemetry on the correct vertical dashboard.
- [ ] Trigger a representative abnormal condition and verify the alert.
- [ ] Verify real email and approved WhatsApp notification delivery.
- [ ] Acknowledge the alert and create/update the work item.
- [ ] Restore the normal condition and show recovery.
- [ ] Disconnect the network, collect buffered samples, reconnect, and verify replay.
- [ ] Power-cycle the CM4 and verify unattended recovery.
- [ ] Have a non-developer complete the owner journey while the team observes silently.
- [ ] Record time to first data, support interventions, confusing words, errors, screenshots, and pass/fail.

Replay release gate:

- [ ] Gateway activation succeeds when the Gateway is offline at claim and comes online later.
- [ ] Two authenticated Gateways cannot publish telemetry, attributes, logs, or command responses as one another.
- [ ] Cross-tenant Site/Gateway/Device identifiers are rejected in all onboarding and quick-add mutations.
- [ ] All three verticals score at least 2/3 on every core journey.
- [ ] Onboarding and confidence in the live dashboard score 3/3.
- [ ] No P0 remains.
- [ ] Every P1 has a fix completed before handout or a short, tested support script assigned to an owner.

If a vertical fails its replay, hold that vertical's kits. Do not block a proven vertical merely to preserve an artificial all-or-nothing launch.

## 7. Customer Handover Pack

Prepare one physical and digital pack per customer:

- [ ] Welcome letter stating the customer's selected outcome and trial dates.
- [ ] One-page illustrated quick start for the correct vertical.
- [ ] Box contents and serial number list.
- [ ] Site/network/power prerequisites.
- [ ] Installation drawing for the exact approved connection.
- [ ] Clear “do not open or wire this panel yourself” warning where applicable.
- [ ] Supported equipment and scope statement.
- [ ] Login URL and named user invitation; never print a reusable shared password.
- [ ] Ten-minute owner guide: dashboard, last update, alert, acknowledgement, and getting help.
- [ ] Short installer guide separated from the business-owner guide.
- [ ] Troubleshooting guide limited to safe actions: check power, cable, network, displayed status, and contact support.
- [ ] Support hours, WhatsApp/email/phone contact, and kit serial.
- [ ] Pilot agreement, equipment-loan/return terms, and privacy/data notice reviewed by appropriate counsel.
- [ ] Feedback schedule and conversion decision date.
- [ ] QR codes to login, help, and support tested from a normal phone.

## 8. Support and Field Operations for 20 Customers

- [ ] Create one official pilot support channel and tell customers not to contact individual developers.
- [ ] Create a customer-visible response policy: P0 within 1 hour during pilot support hours, P1 within 4 business hours, P2 by the next business day.
- [ ] Publish support hours and special coverage for 29 July–3 August.
- [ ] Create a daily health board showing customer, gateway online state, equipment data freshness, last alert, open issue, next appointment, and support owner.
- [ ] Create an internal issue log with P0/P1/P2, customer impact, workaround, owner, and next update time.
- [ ] Define the remote-diagnostics consent and access procedure.
- [ ] Drill gateway replacement: identify failure, assign spare, provision it, deliver it, and recover service.
- [ ] Keep three packed spares split across the most likely accessory configurations.
- [ ] Hold a 15-minute launch triage daily during the rollout; discuss customer impact before feature ideas.
- [ ] Send customers a concise status update whenever their issue is not resolved within the promised response window.
- [ ] Give each vertical sales owner a technical escalation path, but prohibit them from promising dates or custom features without triage.

## 9. Pilot Learning and Commercial Validation

The trial is not only a bug hunt. It must test whether Novena delivers a valuable, repeatable outcome that SMEs will buy.

For every customer:

- [ ] Record the pre-pilot baseline and desired measurable outcome.
- [ ] Record setup time from opening the kit to first trustworthy data, excluding planned electrical installation.
- [ ] Record Novena staff minutes required for site survey, configuration, installation, training, and weekly support.
- [ ] Record every point where a customer asks for technical help.
- [ ] Record days with fresh telemetry and unexplained data gaps.
- [ ] Record meaningful alerts, false/nuisance alerts, acknowledged alerts, and actions taken.
- [ ] Record dashboard, weekly-summary, export, and maintenance usage.
- [ ] Ask after onboarding: “Without our help, could you explain what Novena is telling you and what to do next?”
- [ ] Run a 15-minute weekly check-in focused on outcome, confusion, trust, and missing workflow.
- [ ] Do not promise every requested feature. Tag feedback as common-horizontal, vertical-configuration, one-customer customization, or later AI opportunity.
- [ ] Ask for willingness to pay and the buying approver before the final week.
- [ ] Complete a conversion review before the trial ends: subscribe, extend with a defined reason, or return the kit.

### Cohort success measures

- [ ] At least 18 of 20 customers complete installation and reach first trustworthy data.
- [ ] Median software onboarding time is 30 minutes or less after approved physical wiring/networking is ready.
- [ ] At least 16 of 20 can explain their dashboard and next action without a developer.
- [ ] At least 90% of pilot days have fresh expected telemetry, excluding documented customer outages.
- [ ] No cross-customer data exposure, unsafe command, or false “healthy” state occurs.
- [ ] Median Novena support effort after week one is no more than 30 minutes per customer per week.
- [ ] At least 10 customers use or act on a dashboard, alert, summary, or maintenance workflow weekly.
- [ ] At least 8 customers give a concrete paid continuation signal, with at least 5 ready for a defined paid plan or follow-on pilot.

These targets are hypotheses. Keep the measured result even when it is uncomfortable; that is the information the pilot is meant to produce.

## 10. Two-Week Execution Calendar

### 18–20 July: Freeze scope and qualify the cohort

- [ ] Name all role owners.
- [ ] Approve pilot scope, terms, support promise, no-custom-code rule, and go/hold authority.
- [ ] Rank at least 25 prospects so five substitutes exist.
- [ ] Send the site survey and request equipment/network photos and documents.
- [ ] Assign provisional 7/7/6 vertical slots without accepting weak-fit sites.
- [ ] Lock the pilot bill of materials and confirm 23-unit availability.

### 21–23 July: Match sites, freeze software, build kits

- [ ] Complete all 20 site compatibility decisions.
- [ ] Approve the exact templates and connection plans.
- [ ] Freeze the Hub and Gateway pilot release candidates.
- [ ] Complete the common Hub journey and vertical outcome-pack P0/P1 fixes.
- [ ] Image, label, inventory, and begin bench testing the 23 gateways.
- [ ] Prepare customer accounts, sites, invitations, and gateway assignments.
- [ ] Finalize pilot, loan, privacy, installation, and support documents.

### 24–26 July: Prove hardware and usability

- [ ] Run the energy, cold-chain, and facilities CM4 hardware replays.
- [ ] Update the pilot scorecard with real results.
- [ ] Run a silent usability test with a non-developer for each vertical.
- [ ] Fix P0 findings immediately; decide fix/script/hold for every P1.
- [ ] Start the 24-hour burn-in for all customer and spare gateways.
- [ ] Test real email/WhatsApp alerts and customer-facing report/export output.

### 27–28 July: Pack, rehearse, and make the first gate decision

- [ ] Complete burn-in, second-person signoff, and packing.
- [ ] Match every box to the customer, accessories, account, and install plan.
- [ ] Test every QR code, invitation, guide, and support route.
- [ ] Run an internal support drill, replacement drill, and full handover rehearsal.
- [ ] Review all 20 rows and remove/defer any customer with an unresolved qualification item.
- [ ] Select five canary customers: two energy, two cold-chain, and one facilities/hospitality, adjusted only for qualification quality.

### 29 July: Release the five-customer canary wave only if Gate A is complete

- [ ] Hand over/install five kits.
- [ ] Observe onboarding without taking control unless the customer is blocked or safety is involved.
- [ ] Capture time to first data, interventions, issues, and customer confidence.
- [ ] Monitor gateway and equipment freshness for at least 24 hours.

### 30 July: Canary go/hold review

- [ ] At least 4 of 5 customers reach first trustworthy data.
- [ ] Median software onboarding time is 30 minutes or less after physical prerequisites are ready.
- [ ] No P0 is open.
- [ ] No repeated issue affects more than one customer without a tested fix or support script.
- [ ] Support load is sustainable and the three spares remain ready.
- [ ] Launch owner records **GO**, **PARTIAL GO**, or **HOLD** by vertical.

### 31 July: Controlled release to the remaining 15

- [ ] Release only customers and verticals that passed the gate.
- [ ] Confirm handover, installation date, support owner, and first follow-up for each customer.
- [ ] Send the cohort welcome message and support schedule.
- [ ] Begin the daily health review and customer feedback cadence.
- [ ] Publish the final launch register: 20 released, partially released, deferred, or substituted—with reasons.

## 11. Final Go / Partial-Go / Hold Checklist

### GO when all are true

- [ ] The CTO review's activation, MQTT identity, tenant-scoping, OTA trust/disablement, and reproducible-release blockers are closed.
- [ ] Twenty customers are qualified, signed, assigned, and scheduled.
- [ ] Twenty customer kits plus three spares passed acceptance and burn-in.
- [ ] Every target equipment model has an approved, evidenced template and connection plan.
- [ ] All three real CM4 vertical replays passed the product-readiness gates.
- [ ] The five-customer canary passed the 30 July thresholds.
- [ ] No P0 is open and every P1 has an owner and tested resolution or support script.
- [ ] Customer materials, support channel, daily health board, and replacement process are live.
- [ ] The launch owner signs and dates the decision.

### PARTIAL GO when

- [ ] One vertical or equipment family is unproven, but other customer journeys passed independently.
- [ ] Only passed sites receive kits; affected customers receive an honest revised date.
- [ ] Deferred customers are replaced from the qualified reserve list where possible.

### HOLD a customer or vertical when any is true

- [ ] Equipment identity, protocol, safe connection, or site authorization is unknown.
- [ ] A template is marked verified without exact-device evidence.
- [ ] Setup still requires SSH, source changes, or manual JSON/register engineering at the customer site.
- [ ] Telemetry values, units, scaling, customer isolation, freshness, alerts, or recovery cannot be trusted.
- [ ] The physical install requires an unavailable qualified person.
- [ ] A gateway fails burn-in or cannot recover from network/power interruption.
- [ ] Support capacity or a replacement unit is unavailable.

## 12. Twenty-Customer Launch Register

Use one row per customer. Link detailed survey, agreement, and evidence rather than placing sensitive information in this document.

| ID | Customer | Vertical | Outcome / asset | Equipment model | Fit | Kit serial | Survey | Agreement | Bench | Handover / install | First data | Support owner | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C01 |  | Energy |  |  |  |  | [ ] | [ ] | [ ] |  | [ ] |  | Candidate |
| C02 |  | Energy |  |  |  |  | [ ] | [ ] | [ ] |  | [ ] |  | Candidate |
| C03 |  | Energy |  |  |  |  | [ ] | [ ] | [ ] |  | [ ] |  | Candidate |
| C04 |  | Energy |  |  |  |  | [ ] | [ ] | [ ] |  | [ ] |  | Candidate |
| C05 |  | Energy |  |  |  |  | [ ] | [ ] | [ ] |  | [ ] |  | Candidate |
| C06 |  | Energy |  |  |  |  | [ ] | [ ] | [ ] |  | [ ] |  | Candidate |
| C07 |  | Energy |  |  |  |  | [ ] | [ ] | [ ] |  | [ ] |  | Candidate |
| C08 |  | Cold chain |  |  |  |  | [ ] | [ ] | [ ] |  | [ ] |  | Candidate |
| C09 |  | Cold chain |  |  |  |  | [ ] | [ ] | [ ] |  | [ ] |  | Candidate |
| C10 |  | Cold chain |  |  |  |  | [ ] | [ ] | [ ] |  | [ ] |  | Candidate |
| C11 |  | Cold chain |  |  |  |  | [ ] | [ ] | [ ] |  | [ ] |  | Candidate |
| C12 |  | Cold chain |  |  |  |  | [ ] | [ ] | [ ] |  | [ ] |  | Candidate |
| C13 |  | Cold chain |  |  |  |  | [ ] | [ ] | [ ] |  | [ ] |  | Candidate |
| C14 |  | Cold chain |  |  |  |  | [ ] | [ ] | [ ] |  | [ ] |  | Candidate |
| C15 |  | Facilities / hospitality |  |  |  |  | [ ] | [ ] | [ ] |  | [ ] |  | Candidate |
| C16 |  | Facilities / hospitality |  |  |  |  | [ ] | [ ] | [ ] |  | [ ] |  | Candidate |
| C17 |  | Facilities / hospitality |  |  |  |  | [ ] | [ ] | [ ] |  | [ ] |  | Candidate |
| C18 |  | Facilities / hospitality |  |  |  |  | [ ] | [ ] | [ ] |  | [ ] |  | Candidate |
| C19 |  | Facilities / hospitality |  |  |  |  | [ ] | [ ] | [ ] |  | [ ] |  | Candidate |
| C20 |  | Facilities / hospitality |  |  |  |  | [ ] | [ ] | [ ] |  | [ ] |  | Candidate |

Allowed status values: **Candidate**, **Qualified**, **Kit ready**, **Scheduled**, **Canary**, **Launched**, **Deferred**, or **Returned**.

## Founder/CTO View

The main risk in the next two weeks is not a missing AI feature. It is promising one uniform plug-and-play experience across twenty unknown site environments before proving the exact equipment and connection path. The product strategy remains strong if Novena treats the gateway, verified equipment template, vertical outcome pack, installation method, and support script as one repeatable product unit.

Success on 31 July is therefore not measured by how many boxes leave the office. It is measured by how many qualified customers receive a controlled, trustworthy path to first value—and how quickly Novena learns which parts can be repeated without founder engineering.
