# Novena Physical Operations Platform Roadmap

> Date: 11 August 2026
> Owner perspective: CTO and Chief Product Officer
> Scope: Novena Hub, Novena Gateway, product strategy, vertical expansion, and APJC scale path

## Executive Thesis

Novena should become the physical operations platform for industrial and commercial facilities in APJC by turning brownfield equipment into a trusted, standardized operational model, then layering workflows, automation, maintenance, reporting, and AI on top.

The long-term vision is broad:

- Sites: factories, data centres, warehouses, cold storage, hotels, hospitals, commercial buildings, food manufacturing, utilities, water systems, renewable energy sites, industrial estates.
- Devices: power meters, PLCs, VFDs, chillers, compressors, pumps, HVAC, boilers, solar inverters, generators, cold rooms, industrial sensors.

The near-term execution must stay narrow. Novena is not mature enough to be a universal physical operations platform today, and it should not sell like one yet. The correct path is to build a repeatable wedge, prove trust in the field, then expand by vertical and device family.

The guiding architecture remains:

```text
LEGACY PHYSICAL WORLD
        |
        | Novena Gateway
        v
STANDARDIZED OPERATIONAL MODEL
        |
        | Novena Hub
        v
CLOUD DATA + WORKFLOWS
```

The product unit is:

```text
Managed Novena Gateway
+ verified equipment template
+ vertical outcome pack
+ safe installation method
+ remote support workflow
```

This is the unit Novena should repeat until it becomes an operating system for physical infrastructure.

## Current State

Novena currently has the correct spine for the future platform:

- Hub models sites, gateways, devices, templates, telemetry, alerts, automations, maintenance, remote control, and business impact.
- Gateway is a managed edge runtime with serial-scoped MQTT, local buffering, remote config, diagnostics, discovery, signed setup, and governed write-back foundations.
- Product direction already focuses on energy monitoring, cold chain, facilities/HVAC, and PLC/generic I/O.
- Recent work has improved identity, activation, tenant isolation, guided setup, live telemetry, and PLC datapoint mapping.

Current strength:

- Modbus TCP/RTU equipment.
- Power meters.
- VFDs.
- Temperature/cold-room monitoring.
- PLC/generic I/O where Novena can map site-defined datapoints.
- Facilities/HVAC monitoring as an early vertical, especially where Modbus equipment is present.

Current limitation:

- The platform data model is broad, but the productized connector/config path is still Modbus-first.
- BACnet, OPC-UA, SNMP, MQTT bridge, and other protocols exist more as Gateway potential than complete Hub-led product experiences.
- The device library is not yet deep enough to claim broad industrial coverage.
- Hardware replay and 3-5 customer canary evidence remain the main launch gates.

## Strategic Principles

### 1. Narrow wedge first, broad platform later

Novena should not start by selling "we support all facilities and all equipment." That creates support chaos. Start with a tight wedge where Novena can create repeatable success, then expand from verified evidence.

The first winning wedge should be:

```text
Factory energy and equipment monitoring
with power meters, VFDs, PLC/generic I/O, and selected cold/facilities assets.
```

Energy remains the best first commercial wedge because the customer value is measurable, budgets are easier to justify, and power meters are common.

### 2. Every expansion must be evidence-backed

A device or vertical is not "supported" because a connector exists. It is supported only when Novena has:

- Exact make/model or approved generic class.
- Protocol and connection method.
- Verified datapoints.
- Units, scaling, byte order, polling behavior, valid ranges.
- Dashboard meaning.
- Alert presets.
- Installation guide.
- Field evidence.
- Support playbook.

This is how Novena avoids becoming a custom systems-integration business.

### 3. Standardize the operational model, not the physical world

Brownfield equipment will always be messy. The product should not try to make every site identical at the wiring/protocol level. Instead, Novena should standardize what the cloud sees:

- Site.
- Area or asset group.
- Gateway.
- Equipment.
- Datapoint.
- State.
- Event.
- Alert.
- Work item.
- Business impact.

This is the core product architecture. Protocols are adapters into this model.

### 4. Monitoring before control

Write-back and automation are powerful but risky. Novena should scale monitoring first, then introduce control only when there is enough evidence, commissioning, policy, role approval, emergency disablement, and post-action verification.

Default commercial posture:

```text
Phase 1: read-only monitoring
Phase 2: assisted diagnostics
Phase 3: governed write-back for selected low-risk actions
Phase 4: closed-loop optimization only after field trust
```

### 5. AI is downstream of trusted operations data

AI should not be the product foundation yet. It becomes valuable after Novena has reliable telemetry, asset context, alerts, work history, maintenance outcomes, and business-impact baselines.

AI should evolve from:

- "Explain this alert."
- "Summarize weekly site performance."
- "Suggest likely causes."
- "Recommend maintenance actions."
- "Compare sites."
- "Optimize operations within approved constraints."

## Stage Roadmap

## Stage 0: Release Candidate Trust Closure

Target: now to technical canary.

Mission:

Prove that the Hub/Gateway spine is trustworthy enough for supervised customer use.

Primary verticals:

- Factory energy.
- Cold chain.
- Facilities/HVAC.
- General PLC/generic I/O for assisted setup.

Device focus:

- Power meters.
- VFDs.
- Modbus temperature/humidity sensors.
- Cold-room door/compressor signals.
- PLC/generic I/O via site-defined datapoint maps.
- Selected chiller/HVAC assets only when Modbus-backed or otherwise controlled.

Product work:

- Complete CM4 hardware replays for factory-energy, cold-chain, and facilities/HVAC.
- Confirm offline buffering across restart and reconnect.
- Confirm first telemetry reaches the correct device and tenant.
- Confirm guided setup can validate datapoints before deployment.
- Confirm customer-safe states: Gateway online, equipment not reporting, delayed telemetry, browser polling fallback.
- Keep control disabled by default except for explicitly reviewed internal tests.

Technical work:

- Finish physical replay evidence for MQTT identity, buffering, config delivery, activation, and telemetry freshness.
- Harden production Stripe, WhatsApp inbound security, and production environment checks before paid rollout.
- Keep Gateway release reproducible from clean checkout.
- Maintain serial-scoped MQTT and signed configuration as non-negotiable platform boundaries.

Commercial work:

- Run a 3-5 customer technical canary.
- One site, one Gateway, one primary asset or one identical asset group per customer.
- Measure time to first data, support minutes, installation effort, customer weekly usage, and conversion intent.

Exit criteria:

- 3 vertical hardware replays pass.
- At least 4 of 5 canary sites reach trustworthy first data.
- No P0 tenant, identity, activation, or false-healthy issue.
- Support burden is understood and bounded.
- One vertical shows the clearest paid-conversion signal.

Leadership guidance:

Do not widen to 20 customers just because the product feels feature-rich. Widen only after first-data reliability and support cost are proven.

## Stage 1: First Repeatable Commercial Wedge

Target: first 10-30 paying or committed design-partner customers.

Mission:

Turn the strongest canary vertical into a repeatable, sellable product package.

Recommended lead wedge:

```text
Factory and commercial energy monitoring
```

Why:

- Clear ROI language.
- Common equipment.
- Strong fit with Singapore and ASEAN digitization narratives.
- Power meters and VFDs are practical first templates.
- Energy data can feed alerts, reports, and business-impact calculations.

Product package:

- Managed Gateway.
- One energy outcome pack.
- Verified meter/VFD templates.
- First-data acceptance test.
- Live demand and energy trend.
- Abnormal demand alert.
- Weekly energy summary.
- Maintenance/ticket workflow for abnormal equipment states.

Device expansion:

- More power-meter families.
- More VFD families.
- Solar inverters where Modbus TCP is common.
- PLC/generic I/O as an assisted bridge for machines without direct metering.

Platform work:

- Build a formal template trust registry.
- Add template evidence fields: exact model, source document, version, verification method, field evidence, approval status, supported firmware notes.
- Add an equipment compatibility intake flow for sales and support.
- Improve template request workflow from "support ticket" into a structured equipment qualification pipeline.

Go-to-market:

- Founder-led sales.
- Partner with electricians, controls technicians, and energy auditors.
- Sell a time-boxed energy visibility offer, not a generic IoT platform.
- Separate subscription, Gateway assurance, installation, and accessories.

Metrics:

- Median time from installation to first trustworthy data.
- Median support minutes in week 1 and week 4.
- Number of verified templates reused across customers.
- Conversion rate from design partner to paid.
- Expansion from one asset to more assets/sites.

Exit criteria:

- 20+ successful first-data deployments in one lead wedge.
- At least 10 repeat uses of verified templates.
- Support playbook works without founder engineering on every site.
- Pricing can cover hardware, support, and cloud cost.

Leadership guidance:

Do not overbuild AI or dashboards before repeatability. The moat at this stage is verified templates plus a supportable Gateway, not visual polish alone.

## Stage 2: Multi-Vertical SME Operations Platform

Target: 30-150 customers.

Mission:

Expand from one wedge into 3-4 repeatable vertical outcome packs while keeping one shared platform.

Verticals:

- Energy monitoring.
- Cold chain and food safety.
- Facilities/HVAC and maintenance coordination.
- Light manufacturing visibility through PLC/generic I/O.

Device coverage:

- Power meters.
- VFDs.
- PLCs.
- Temperature/humidity sensors.
- Door sensors.
- Chillers.
- Compressors.
- Pumps.
- Solar inverters.
- Industrial sensors.

Product work:

- Create vertical dashboards that prioritize business questions, not raw registers.
- Add site-type presets for factories, cold rooms, warehouses, hotels, clinics, commercial buildings, and food manufacturing.
- Add operational reports per vertical:
  - Energy: kWh, peak demand, after-hours load, abnormal events, data coverage.
  - Cold chain: excursions, duration, acknowledgement, action history, sensor coverage.
  - Facilities: equipment status, runtime, open work, contractor actions, recurring issues.
  - Manufacturing: line status, machine state, downtime signals, throughput-adjacent telemetry where available.

Technical work:

- Add BACnet productization for facilities/HVAC.
- Add OPC-UA productization for manufacturing environments.
- Add SNMP/MQTT bridge support where data centres or utilities need it.
- Create protocol-specific config generators in Hub instead of relying on Modbus-only generation.
- Add protocol capability flags to Gateway and template compatibility.
- Build an equipment semantic layer so `active_power`, `run_status`, `temperature`, `flow_rate`, and `pressure` mean consistent things across protocols.

Operational work:

- Create customer success health dashboards.
- Add deployment evidence records to every site.
- Build playbooks for common faults:
  - Gateway offline.
  - Gateway online, device offline.
  - Values implausible.
  - Network blocked.
  - RS485 wiring issue.
  - Template mismatch.
  - Sensor drift.

Go-to-market:

- Hire or appoint vertical owners.
- Build installer and controls-partner certification.
- Create supported-equipment catalogues by vertical.
- Use land-and-expand: one site and one use case first, then more assets/sites.

Metrics:

- Gross margin including support and Gateway assurance.
- Template reuse rate.
- Percentage of deployments not requiring code changes.
- Alert-to-action completion rate.
- Weekly active operational users.
- Number of multi-site expansions.

Exit criteria:

- 3-4 vertical packs repeat with non-founder delivery.
- Protocol support includes productized Modbus plus at least one of BACnet or OPC-UA.
- Support burden trends down as template library grows.
- First multi-site customers renew or expand.

Leadership guidance:

At this stage, protect the common platform. Do not allow each vertical to become its own code fork. Vertical differences should live in templates, dashboards, presets, reports, and workflow configuration.

## Stage 3: Physical Operations System of Record

Target: 150-750 customers.

Mission:

Make Novena the system of record for physical operational events across facilities, assets, maintenance, alerts, energy, and work history.

Expanded sites:

- Factories.
- Warehouses.
- Cold storage.
- Hotels.
- Hospitals and clinics.
- Commercial buildings.
- Food manufacturing.
- Renewable energy sites.
- Water and pump systems.

Expanded devices:

- Power meters.
- PLCs.
- VFDs.
- Chillers.
- Compressors.
- Pumps.
- HVAC controllers.
- Boilers.
- Solar inverters.
- Generators.
- Cold rooms.
- Industrial sensors.

Product work:

- Asset registry with site, area, equipment, criticality, manufacturer, model, service owner, and maintenance policy.
- Event timeline per site and asset.
- Operational state model:
  - running.
  - stopped.
  - fault.
  - unavailable.
  - manual/hand mode.
  - maintenance.
  - degraded.
  - unknown.
- Maintenance intelligence:
  - recurring fault patterns.
  - time-to-acknowledge.
  - time-to-resolve.
  - contractor performance.
  - evidence attachments.
- Business impact:
  - cost of downtime.
  - energy waste.
  - cold-chain risk.
  - maintenance labor.
  - avoided incidents where evidence supports it.

Technical work:

- Build a semantic asset ontology.
- Add data-quality scoring per datapoint.
- Add calibration/sensor confidence where relevant.
- Improve telemetry storage lifecycle by plan and customer value.
- Add APIs for enterprise integrations.
- Add role-based multi-site command center.
- Add fleet analytics across Gateway hardware, protocol success, template coverage, and support signals.

AI work:

- Site copilot that explains current state and recent changes.
- Alert triage assistant.
- Maintenance summary assistant.
- Template-assist workflow for Novena support, with human verification required.
- Cross-site anomaly detection for similar equipment.

Go-to-market:

- Build industry-specific playbooks.
- Expand APJC via channel partners after Singapore repeatability.
- Create partner certification for installation, support, and template contribution.
- Move from founder-led sales to vertical sales pods.

Metrics:

- Net revenue retention.
- Sites per customer.
- Assets per site.
- Verified-template contribution velocity.
- Percentage of alerts tied to completed actions.
- Reduction in support minutes per deployed Gateway.
- Expansion revenue by vertical.

Exit criteria:

- Novena is used weekly by operations teams, not only checked during incidents.
- Multi-site customers treat Novena as an operating layer.
- Partner delivery can deploy supported use cases without custom engineering.
- AI recommendations are grounded in trusted telemetry and workflow history.

Leadership guidance:

The company must start behaving less like a project team and more like a platform company. Formalize platform APIs, partner quality, security reviews, customer success operations, and template governance.

## Stage 4: APJC Physical Operations Network

Target: 750-3000+ customers and regional expansion.

Mission:

Scale Novena from a strong SME platform into a regional physical operations network across APJC.

Expanded sites:

- Industrial estates.
- Multi-tenant commercial portfolios.
- Data centres.
- Utilities.
- Water systems.
- Renewable energy fleets.
- Large food manufacturing and logistics networks.
- Hospitals and regulated facilities where evidence requirements are satisfied.

Expanded capabilities:

- Regional fleet operations.
- Benchmarking across similar assets.
- Partner marketplace for templates and installation services.
- Enterprise integrations.
- Regulated evidence packs where the product can truly support them.
- Advanced optimization and controlled automation for approved use cases.

Technical work:

- Multi-region architecture.
- Enterprise SSO and audit exports.
- Tenant data residency choices where needed.
- Partner/template review workflow.
- High-scale telemetry ingestion and retention tiers.
- Stronger observability and incident response.
- Fleet OTA with staged rollout, signed manifests, rollback, and hardware cohort targeting.

Commercial work:

- Country playbooks for Singapore, Malaysia, Indonesia, Thailand, Vietnam, Philippines, Australia, Japan, and Korea where justified by partner/customer pull.
- Strategic channel partnerships with controls firms, energy-service companies, facilities managers, refrigeration specialists, and equipment OEMs.
- Enterprise account motion for multi-site operators.
- Marketplace or certification revenue from partners.

Defensibility:

- Verified equipment graph.
- Deployment and support evidence.
- Cross-site operational benchmarks.
- Regional partner network.
- Historical maintenance/action data.
- Trustworthy AI built on real operational context.

Exit criteria:

- Novena is the default physical operations layer for a measurable category of APJC SMEs and mid-market operators.
- The company can expand into new device/site categories through a repeatable template and partner system.
- Platform value increases as more customers, assets, templates, and operational events are added.

Leadership guidance:

Do not confuse regional expansion with translation and sales hiring. Regional expansion requires installation capacity, support workflows, device compatibility knowledge, regulatory awareness, hardware logistics, and local partner trust.

## Expansion Matrix

| Expansion area | Start now | Add next | Mature-state coverage |
| --- | --- | --- | --- |
| Sites | Factories, cold rooms, commercial facilities | Warehouses, hotels, food manufacturing, renewable sites | Data centres, hospitals, utilities, water systems, industrial estates |
| Devices | Power meters, VFDs, PLC/generic I/O, temp sensors | Pumps, compressors, chillers, solar inverters, industrial sensors | Boilers, generators, HVAC/BMS controllers, water systems, utility equipment |
| Protocols | Modbus TCP/RTU | BACnet, OPC-UA, MQTT bridge | SNMP, CAN, OCPP, REST, vendor APIs, enterprise integrations |
| Workflows | Dashboards, alerts, maintenance tickets | Preventive maintenance, weekly reports, support diagnostics | Optimization, benchmarking, partner marketplace, governed automation |
| AI | Explain alerts and summarize trends | Triage, root-cause suggestions, template assistance | Cross-site optimization, predictive maintenance, operational copilots |

## Product Architecture Direction

Novena should evolve around six platform layers.

### Layer 1: Connectivity

Purpose:

Connect brownfield equipment safely through Gateway.

Roadmap:

- Modbus TCP/RTU first.
- BACnet for facilities/HVAC.
- OPC-UA for manufacturing.
- SNMP and MQTT bridge for data centres/utilities.
- Vendor APIs only when they are repeatable and commercially important.

### Layer 2: Standardized Operational Model

Purpose:

Convert protocol-specific readings into business-meaningful operational signals.

Core objects:

- Site.
- Gateway.
- Asset/device.
- Datapoint.
- State.
- Event.
- Alert.
- Work item.
- Business impact metric.

This layer is the heart of Novena. It is what allows a chiller, PLC, VFD, power meter, or cold room to become understandable in one cloud product.

### Layer 3: Trust and Evidence

Purpose:

Make customers believe the data.

Requirements:

- Verified templates.
- Live validation.
- Plausibility checks.
- Data-quality score.
- Last-seen/freshness states.
- Installation evidence.
- Calibration and sensor placement notes where needed.
- Support-visible diagnostics.

### Layer 4: Workflows

Purpose:

Turn readings into operational action.

Workflows:

- Alerts.
- Acknowledgement.
- Escalation.
- Maintenance tickets.
- Preventive schedules.
- Contractor access.
- Reports.
- Impact reviews.

### Layer 5: Control and Automation

Purpose:

Allow approved actions only when Novena can prove safety boundaries.

Roadmap:

- Read-only monitoring by default.
- Diagnostic reads.
- Human-approved write-back for low-risk devices.
- Policy-bound control with emergency disable.
- Closed-loop optimization only for mature, verified use cases.

### Layer 6: Intelligence

Purpose:

Help operators understand, decide, and improve.

Roadmap:

- Summaries.
- Root-cause suggestions.
- Operational recommendations.
- Cross-site comparison.
- Predictive maintenance.
- Optimization.

## Device-Family Roadmap

### Power meters

Role:

Best first wedge for energy visibility and ROI.

Build:

- Deep verified template library.
- Energy dashboard.
- Peak demand alerts.
- After-hours load detection.
- Tariff-aware impact calculations.

### PLCs and generic I/O

Role:

Bridge into machines and brownfield systems where no standard equipment template exists.

Build:

- Site-defined datapoint maps.
- CSV import/export.
- Live validation.
- Clone maps across similar sites.
- Semantic labels and units.
- Strict read/write separation.

### VFDs

Role:

High-value equipment monitoring for motors, pumps, fans, and compressors.

Build:

- Runtime, speed, current, power, fault, run status.
- Monitoring first.
- Governed write-back later for setpoints only after commissioning.

### Cold rooms and industrial sensors

Role:

Cold-chain product wedge.

Build:

- Temperature, humidity, door state, compressor state.
- Excursion alerts and evidence history.
- Sensor placement/calibration notes.
- Audit-friendly exports without overclaiming compliance.

### Chillers, HVAC, pumps, and compressors

Role:

Facilities and commercial-building expansion.

Build:

- BACnet and Modbus templates.
- Runtime, status, temperature, pressure, flow, power.
- Maintenance workflow presets.
- Fault-state interpretation.

### Solar inverters and generators

Role:

Energy and resilience expansion.

Build:

- Generation, output power, status, alarms.
- Site energy balance.
- Generator runtime and failure alerts.
- Maintenance schedules.

### Boilers, water systems, utilities

Role:

Later-stage infrastructure expansion.

Build only after:

- Stronger safety model.
- Qualified partners.
- Protocol and regulatory confidence.
- Mature support operation.

## Site/Vertical Roadmap

### Factory energy

Start here. It is the clearest wedge.

Customer question:

What is using energy, what changed, and did it recover?

### Cold chain

Second wedge when sensor trust and evidence history are strong.

Customer question:

Is stock at risk, for how long, and who responded?

### Facilities/HVAC

Third wedge, especially for hotels, commercial buildings, clinics, and warehouses.

Customer question:

Which equipment needs attention, what is wrong, and who owns the next action?

### Light manufacturing operations

Use PLC/generic I/O to digitize machine state, downtime signals, and basic production context.

Customer question:

Which line or machine changed state, and what action followed?

### Data centres and utilities

Later-stage wedge. Attractive, but operational expectations are higher.

Customer question:

Are power, cooling, backup, and critical systems healthy across a high-availability site?

### Industrial estates

Mature-stage expansion. Requires multi-tenant physical operations, submetering, shared infrastructure, and partner-led deployment.

Customer question:

What is happening across the estate, which tenant/site is affected, and who should act?

## Commercial Roadmap

### Stage 0-1 pricing

Keep pricing simple, but do not hide field costs inside SaaS.

Revenue components:

- Platform subscription.
- Gateway assurance fee.
- Installation or partner installation.
- Accessories/sensors.
- Expansion services.

### Stage 2 packaging

Create vertical packs:

- Energy Pack.
- Cold Chain Pack.
- Facilities Pack.
- Manufacturing Signals Pack.

Each pack should include:

- Supported equipment list.
- Default dashboard.
- Alert presets.
- Report.
- Installation checklist.
- Support playbook.

### Stage 3-4 monetization

Add:

- Multi-site tier.
- Advanced retention.
- API/enterprise integration.
- AI insights.
- Partner marketplace.
- SLA and dedicated support.
- Template certification or OEM partnerships.

## Organization Roadmap

### Current team posture

Founder-led product and engineering is correct for this stage.

### Next hires or roles

Priority roles:

- Field application engineer: owns first-data success.
- Customer success/operator support: owns weekly usage and support playbooks.
- Hardware/Gateway owner: owns reproducible appliance releases.
- Vertical product owner: starts with energy, later cold chain/facilities.
- Partner/channel lead: only after repeatability is proven.

### Partner ecosystem

Build slowly:

- Electrical contractors.
- Controls technicians.
- Energy auditors.
- Refrigeration service companies.
- Facilities management partners.
- Equipment distributors and OEMs.

Partners should not sell unsupported promises. They need a supported catalogue, installation standards, escalation paths, and commercial incentives tied to successful first data.

## CTO Guidance

1. Preserve the Hub/Gateway trust boundary. Identity, topic scoping, signed config, activation, tenant isolation, and audit trails are platform foundations.
2. Keep Gateway as a managed appliance, not a hobby Pi deployment.
3. Build protocol productization in Hub, not only Gateway connector availability.
4. Treat template verification as core infrastructure.
5. Require hardware replay before broad claims.
6. Keep write-back disabled by default until governed control has field evidence.
7. Invest in support diagnostics early. Support cost can kill the business even when software works.
8. Add observability for deployment outcomes: first data, failed configs, stale devices, reconnects, buffer replay, support interventions.
9. Avoid custom code per customer. Configuration is good; forks are dangerous.
10. Build for APJC reliability realities: unstable networks, mixed equipment, site access constraints, installer variability, and multilingual operations.

## CPO Guidance

1. Sell outcomes, not protocols.
2. Do not call the product universal until the evidence supports it.
3. Use "supported", "assisted", and "deferred" qualification states for every site.
4. Make first trustworthy data the core onboarding milestone.
5. Put freshness and confidence next to every operational claim.
6. Turn every pilot into template, installation, support, and pricing learning.
7. Keep vertical packs narrow enough for customers to understand in one conversation.
8. Use AI as leverage after trust, not as a substitute for trust.
9. Measure weekly use and operational action, not just logins.
10. Make Novena feel like a professional operations product: calm, clear, reliable, and accountable.

## Unicorn Path Hypothesis

Novena can become a unicorn-scale APJC company if it becomes the trusted operating layer between the physical world and cloud workflows for a large number of under-digitized industrial and commercial sites.

The scale path is:

```text
Narrow wedge
-> repeatable deployments
-> verified template library
-> multi-vertical packs
-> partner-led installation
-> multi-site operations
-> regional expansion
-> data and workflow network effects
-> AI-assisted physical operations
```

The most important insight:

Novena should not win by being a generic IoT dashboard. It should win by making brownfield operations repeatable, trustworthy, and actionable for businesses that cannot afford custom industrial transformation projects.

## Next 90 Days

1. Finish hardware replays for factory-energy, cold-chain, and facilities/HVAC.
2. Run the 3-5 customer technical canary.
3. Pick the lead commercial wedge from evidence, not preference.
4. Formalize the template trust registry.
5. Create first-data acceptance records for every deployment.
6. Build the customer/equipment qualification pipeline.
7. Decide Gateway assurance and installation pricing.
8. Harden production billing, WhatsApp security, and deployment readiness.
9. Publish a supported equipment catalogue for the first wedge.
10. Convert canary learning into a 20-customer expansion plan only after the gates are passed.

## Final Product Direction

Current positioning:

```text
Novena is a managed industrial monitoring platform for Singapore and ASEAN SMEs,
starting with energy, cold-chain, facilities, and PLC/generic-I/O use cases.
```

Near-future positioning:

```text
Novena is a managed physical operations platform that connects brownfield equipment
to trusted dashboards, alerts, maintenance workflows, and business-impact reporting.
```

Mature positioning:

```text
Novena is the physical operations platform for APJC industrial and commercial sites,
standardizing equipment data and workflows across energy, facilities, manufacturing,
cold chain, utilities, and infrastructure.
```

The company should earn each sentence in that progression.
