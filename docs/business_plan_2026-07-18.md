# Novena Platform — Updated Business Plan

> **Date:** 18 July 2026  
> **Stage:** Pre-launch / design-partner validation  
> **Related review:** [CTO product progress review](cto_product_progress_review_2026-07-18.md)  
> **Execution plan:** [20-customer pilot launch checklist](20_customer_pilot_launch_checklist_2026-07-31.md)

## Executive Summary

Novena Platform is a managed industrial monitoring product for Singapore and ASEAN SMEs. It combines:

1. A standardized Novena Gateway appliance running on Raspberry Pi CM4-class hardware.
2. Novena Hub, a multi-tenant cloud platform for onboarding, dashboards, alerts, maintenance, and reporting.
3. Verified equipment templates that translate real industrial protocols into trusted business metrics.
4. Vertical outcome packs for energy, cold chain, and facilities operations.
5. Remote diagnostics and support that reduce dependence on custom engineering at every site.

The business thesis remains attractive, but the strategy is now more precise:

> **Novena should win by making a narrow set of industrial monitoring outcomes repeatable for SMEs—not by becoming a universal IoT platform before product-market fit.**

The product has advanced far beyond the April plan. Hub and Gateway are both materially built, the managed-Gateway direction is stronger, and the company can prepare for supervised design partners. However, customer isolation, Gateway activation, tenant scoping, OTA trust, and current CM4 replay evidence must be closed before twenty external kits are released.

The business recommendation is a **conditional go**:

- Fix the launch-blocking trust and commissioning issues.
- Prove three vertical hardware replays.
- Run a 3–5 customer technical canary.
- Expand to the planned twenty only after evidence supports it.
- Use the cohort to choose the strongest paying wedge rather than trying to scale all verticals equally.

## 1. Customer and Problem

### Target customer

The initial buyer is a Singapore SME that owns or operates physical equipment but cannot justify a custom IIoT/SCADA integration project. Typical buyers include:

- Factory owners and operations managers.
- Food manufacturers, cold rooms, distributors, and small cold-chain operators.
- Facilities managers, hospitality operators, and multi-site commercial operators.
- Energy/sustainability managers who need trustworthy equipment-level evidence.

The user is usually not an IoT engineer. The product must answer operational questions without requiring knowledge of MQTT, Modbus, register maps, RPC, JSON, or Linux.

### Jobs to be done

| Vertical | Customer question | Novena outcome |
| --- | --- | --- |
| Energy monitoring | What is using energy, what changed, and did it recover? | Equipment-level power/energy visibility, abnormal-demand alert, weekly summary |
| Cold chain | Is stock at risk, for how long, and who responded? | Temperature/door monitoring, excursion alert, action and history |
| Facilities / hospitality | Which site needs attention, what is wrong, and who owns the next action? | Multi-site status, equipment exception, preventive/reactive work workflow |

### The actual pain

SMEs are not blocked only by dashboard software. They are blocked by the whole last mile:

- Identifying whether their exact equipment can communicate.
- Safely connecting to panels, meters, controllers, or sensors.
- Translating vendor registers and scaling into trustworthy values.
- Surviving unstable customer networks and internet outages.
- Knowing whether the Gateway or the equipment is offline.
- Receiving an alert that explains what happened and what to do.
- Getting help without paying an integrator every time.

Novena's business must package that complete path, not sell software seats detached from field reality.

## 2. Market Rationale

Singapore provides a credible initial market. The official 2024 enterprise landscape reported 356,100 enterprises; SMEs represented 99% of the count, 70% of employment, and 47% of nominal value added. This supports the broad SME thesis, but it is not Novena's serviceable market by itself. The relevant market is the much smaller set of SMEs with monitorable equipment, a measurable operational problem, budget, site access, and supported connectivity. [Singapore Department of Statistics enterprise landscape](https://www.singstat.gov.sg/-/media/Files/visualising_data/infographics/Economy/singapore-economy27032025.pdf)

The immediate market model should therefore be bottom-up:

1. Count qualified sites reachable through founder sales, vertical sales specialists, installers, and industry partners.
2. Record the equipment families and use cases in that pipeline.
3. Estimate revenue only from supported configurations and a realistic conversion rate.
4. Expand the serviceable market as verified templates and installation partners grow.

Do not use a large ASEAN IIoT forecast as evidence that Novena can acquire customers. The next proof is five paid design partners with repeatable support economics.

### Government-program context

Singapore's policy environment can help demand, but Novena must not promise grant eligibility before qualification:

- The Energy Efficiency Grant currently provides support for eligible energy-efficiency equipment, including a base tier for pre-approved equipment with a cap and stated SME support rates. Novena monitoring hardware/software is **not automatically eligible** merely because it measures energy. [Enterprise Singapore EEG](https://www.enterprisesg.gov.sg/EEG)
- SMEs Go Digital describes pre-approved market-proven solutions with grant support of up to 50%. Novena would need to satisfy the relevant vendor/solution process; this is a roadmap, not a current sales entitlement. [IMDA SMEs Go Digital](https://www.imda.gov.sg/How-We-Can-Help/smes-go-digital)
- The Enterprise Development Grant can support eligible transformation projects, but applications are assessed by project scope, outcomes, company eligibility, and provider competency. [Enterprise Singapore EDG](https://www.enterprisesg.gov.sg/financial-support/enterprise-development-grant)

Sales wording should be “grant-aligned documentation” or “we can help assess fit,” never “grant approved” until Novena and the exact offer have been accepted under the relevant program.

## 3. Product and Defensible Advantage

### The standardized product unit

Novena should sell a repeatable unit:

> **Managed Gateway + exact-device template + vertical outcome pack + safe installation method + remote support.**

The horizontal platform remains common across all customers. Vertical differentiation is configuration and workflow:

- Onboarding language.
- Dashboard metric priority.
- Alert presets and recommended action.
- Weekly summaries and exports.
- Maintenance defaults.
- Equipment templates and installation guides.

Customer-specific code forks are prohibited during the design-partner stage.

### Why the Gateway matters commercially

The recent Gateway hardening adds business value in four ways:

1. **Lower support cost:** Hardware/network/config diagnostics can reduce blind troubleshooting.
2. **Higher trust:** TLS, credential lifecycle, secret redaction, connector status, and explicit startup state support a professional appliance story.
3. **Lower service interruption:** Offline buffering, reconnect, last-known-good configuration, and rollback reduce truck rolls.
4. **Fleet leverage:** Remote config and eventual secure OTA make a larger installed base manageable.

These benefits are not fully monetizable until the hardened release is committed, Hub surfaces the diagnostics, and CM4/site evidence confirms the behavior.

### Moat hypothesis

Novena's defensibility is not the use of MQTT, Django, or Raspberry Pi. Those are available to competitors. The moat can emerge from:

- A growing library of exact-device, field-evidenced templates.
- Commissioning data and diagnostic patterns that reduce time to first data.
- Vertical workflow knowledge expressed as outcome packs.
- A reliable Gateway fleet-management and support operation.
- Customer history linking telemetry, alerts, action, and measurable outcome.
- Local installer, electrical, and industry partnerships.

AI becomes defensible only when it learns from trustworthy operational context and produces outcomes customers use. It is not the initial moat by itself.

## 4. Vertical Strategy

### Primary wedge — energy monitoring

Energy remains the best first hypothesis because:

- The buyer can connect monitoring to cost and operational efficiency.
- Power meters and related Modbus equipment are common enough to standardize.
- The product already has energy dashboards, alerts, exports, and template coverage.
- Singapore's energy-efficiency policy context can support customer conversations.

Initial energy offer:

- One site and one primary meter/equipment group.
- Live demand and energy trend.
- Abnormal-demand alert and recovery.
- Weekly summary with energy, peak demand, exceptions, and data coverage.
- No claimed savings unless tariff, baseline, operating context, and comparison method are configured.

### Secondary wedge — cold chain

Cold chain has acute pain and visible alerts, but trust requirements are higher. Sensor accuracy, placement, excursion delay, data continuity, and evidence history must be explicit. Do not claim regulatory compliance until the complete required evidence chain is validated.

### Learning vertical — facilities and hospitality

Facilities can demonstrate multi-site status and maintenance coordination. The segment may have attractive expansion revenue, but equipment diversity and existing BMS/controller environments can increase integration cost. The pilot should test whether Novena can standardize around a small number of HVAC/chiller/pump configurations.

### Cohort allocation

The planned 7 energy / 7 cold-chain / 6 facilities split is useful for learning, but qualification has priority. A supported energy customer is more valuable than an unsupported customer included only to balance a spreadsheet.

After the first cohort, choose the lead wedge using:

- Conversion rate.
- Time to first trustworthy data.
- Installation and support hours.
- Frequency and value of operational actions.
- Expansion potential per site.
- Gross margin after hardware and service.

## 5. Offer and Packaging

### Recommended 60-day design-partner offer

- One Gateway on loan.
- One qualified site.
- One primary monitored asset or one identical equipment group.
- One vertical outcome pack.
- Site survey and compatibility approval before release.
- One assisted onboarding session.
- Defined pilot support hours and replacement procedure.
- Weekly outcome/feedback check-in.
- Clear conversion or return decision date.
- No custom software or unreviewed equipment control.

Use a commitment fee or refundable equipment deposit to filter low-intent prospects. Credit an approved commitment fee toward the first paid term if the customer converts. Final amounts should be set only after the CM4 bill of materials, assembly, installation, replacement reserve, and support cost are measured.

### Current recurring plans

The current code and public content align around this direction:

| Plan | Current public direction | Included capacity | Role |
| --- | ---: | --- | --- |
| Starter | S$99/month | 1 Gateway, up to 5 devices, 7-day visible telemetry history, 10-second interval, email alerts | Low-friction single-site entry |
| Business | S$299/month | 3 Gateways, up to 20 devices, 30-day visible telemetry history, 5-second interval, AI/trend features | Core SME plan |
| Enterprise | Custom | Custom/multi-site capacity; code defaults include up to 100 devices and 90-day visible telemetry history | SLA, larger fleet, implementation needs |

Pricing is still a market hypothesis. It must be validated against support burden and willingness to pay. Also align the remaining legacy `$99/$299/$699` Django pricing template with the Wagtail S$99/S$299/custom public offer before paid launch.

Telemetry history limits are customer-visible access windows, not immediate physical deletion rules. Novena may retain telemetry internally until the global TimescaleDB retention window, currently 90 days, expires. This lets an upgrade reveal previously stored telemetry inside the upgraded plan window while a downgrade immediately reduces customer access without requiring an immediate database purge.

### Revenue model

Novena should separate four revenue components:

1. **Recurring platform subscription:** The core long-term revenue engine.
2. **Gateway assurance:** Sale, lease, or managed-hardware fee covering provisioning, burn-in, replacement reserve, and lifecycle support.
3. **Installation:** A transparent one-time fee or partner quotation for site survey, electrical/controls work, mounting, and commissioning.
4. **Expansion/services:** Additional sites, equipment packs, premium retention, reports, API/SLA, or approved partner integration.

Do not hide installation and field support inside S$99/month. That creates negative-margin customers and trains sales to promise bespoke work.

## 6. Unit Economics — What Must Be Measured

The April business analysis used optimistic ratios without enough product evidence. The updated plan uses explicit measurements.

For every pilot customer record:

- Gateway hardware and accessory cost.
- Assembly, imaging, bench-test, and burn-in labor.
- Freight, replacement, and loss/damage allowance.
- Site-survey and installation hours.
- Novena commissioning and training minutes.
- Weekly support minutes after week one.
- Cloud, telemetry storage, messaging, AI, and payment cost.
- Sales time and any partner commission.
- Recurring revenue and one-time revenue actually collected.

Key formulas:

- **Contribution margin per customer** = recurring revenue + amortized hardware/service revenue − direct cloud, notification, hardware, installation, and support cost.
- **CAC payback** = sales and onboarding acquisition cost ÷ monthly contribution margin.
- **Gateway payback** = delivered Gateway cost ÷ monthly Gateway/platform contribution.
- **Expansion efficiency** = incremental recurring revenue from an additional supported site/device group ÷ incremental field/support cost.

Initial operating targets—not claims of current performance:

- SaaS gross margin above 80% after the field model stabilizes.
- Blended contribution margin above 60% including managed hardware/support.
- CAC payback below 12 months for direct sales and below 9 months for qualified partner leads.
- Median ongoing support below 30 minutes per customer per week after week one.
- A replacement reserve and three ready spares for the first twenty kits.

If the support target cannot be reached, the company must narrow supported equipment, improve diagnostics/onboarding, raise prices, or use paid installation partners before scaling.

## 7. Go-to-Market

### Phase 0 — technical trust and design partners

Current goal:

- Close the CTO review's P0 issues.
- Complete three vertical hardware replays.
- Release 3–5 qualified technical canaries.
- Expand to twenty only after the canary gate passes.

The first cohort is not a broad free trial. It is a managed design-partner program intended to prove repeatability, value, support cost, and willingness to pay.

### Phase 1 — founder-led vertical sales

Use direct outreach and the three vertical sales specialists to qualify pain and equipment before promising a pilot.

Sales sequence:

1. Business problem and baseline interview.
2. Equipment/site/network qualification.
3. Supported/assisted/deferred decision.
4. Outcome-based demo using the same vertical pack.
5. Signed, time-boxed design-partner offer.
6. Installation and first-data acceptance.
7. Weekly outcome review.
8. Paid conversion, justified extension, or return.

Sales compensation should reward successful first data and paid conversion, not boxes handed out.

### Phase 2 — channel leverage

After repeatability is demonstrated, develop partners who already have site access and trust:

- Electrical contractors.
- Controls/automation installers.
- Energy auditors and sustainability consultants.
- Refrigeration/cold-room service companies.
- Facilities management and HVAC service providers.
- Equipment distributors.

Partners need a narrow supported-equipment catalogue, installation standards, diagnostic workflow, and clear commercial split. Do not recruit a large partner network while every deployment still needs founder engineering.

### Phase 3 — Singapore scale and ASEAN expansion

ASEAN expansion should follow operational proof, not precede it. Expansion gates include:

- A repeatable Singapore vertical playbook.
- Remote support that works across sites.
- Local installer/distributor coverage.
- Country-specific connectivity, data, electrical, tax, and support analysis.
- Hardware supply and replacement operations.
- Pricing that covers local support economics.

Malaysia is a logical first regional hypothesis, but the decision should be based on partner access and customer pull rather than geographic ambition alone.

## 8. Pilot Success and Conversion Gates

### Technical canary gate

- All launch P0 issues closed or the risky feature explicitly disabled.
- Current release built from a clean checkout.
- Three real CM4 vertical replays passed.
- 24–48 hour burn-in passed on customer hardware.
- At least four of five canaries reach first trustworthy data.
- No cross-tenant event, false healthy state, unsafe command, or unexplained loss.

### Twenty-customer outcome targets

- At least 18 of 20 complete installation and reach first trustworthy data.
- Median software onboarding is 30 minutes or less after physical prerequisites are ready.
- At least 16 can explain the dashboard and next action without a developer.
- At least 90% of expected pilot days have fresh telemetry, excluding documented customer outages.
- Median Novena support is no more than 30 minutes per customer per week after week one.
- At least 10 customers use or act on a dashboard, alert, summary, or maintenance workflow weekly.
- At least 8 give a concrete paid continuation signal.
- At least 5 are ready for a defined paid plan or follow-on paid deployment.

### Product-market signal

Do not declare product-market fit from positive feedback. Look for:

- Customers paying without a grant being guaranteed.
- Customers using the product when Novena is not prompting them.
- Expansion to another asset/site.
- Referrals to similar operators.
- Declining support time across repeated equipment models.
- A clear lead vertical with predictable sales and delivery.

## 9. Operating Model

### Gateway fleet

- Maintain serialized inventory from factory state through claim, customer assignment, replacement, release, and retirement.
- Use one reproducible image/release per wave.
- Hold three fully provisioned and packed spares for the first twenty customers.
- Record hardware revision, image checksum, burn-in evidence, accessories, and customer/site.
- Never treat an uncommitted developer working tree as a customer release.

### Support

- One official support channel.
- Daily fleet-health review during rollout.
- Clear P0/P1/P2 response commitments.
- Remote diagnostics with customer consent and secret-safe output.
- Tested replacement and restoration procedure.
- Support scripts for known P1 friction; no undocumented founder-only fixes.

### Installation and safety

- Customer owners may connect safe external power/network cables.
- Qualified electricians or controls technicians handle live panels, control wiring, RS-485/BACnet connections, and regulated environments where appropriate.
- Writable commands remain disabled unless separately risk-reviewed for the exact equipment and customer process.

## 10. Risk Register

| Risk | Likelihood | Impact | Response |
| --- | --- | --- | --- |
| Equipment variation turns every site into custom engineering | High | High | Exact-device qualification; narrow template catalogue; defer unsupported sites |
| Cross-tenant MQTT or web mutation | Medium until fixed | Critical | Serial-scoped topics, tenant-scoped queries, isolation tests before pilot |
| Gateway activation fails at first use | High with current ordering | High | Durable activation state, retry on bootstrap, acknowledgement and expiry |
| OTA/control path compromise | Medium | Critical | Disable for canary or signed manifests, strict input/archive validation, least privilege |
| Field networks and wiring consume support capacity | High | High | Site survey, preflight, installer guide/partner, spares, remote diagnostics |
| Pilot customers enjoy free monitoring but do not convert | High | High | Commitment fee, time-boxed pilot, decision date, outcome baseline, paid conversion ask |
| Alert fatigue reduces trust | Medium | High | Vertical presets, delays/cooldowns, review false/nuisance alerts weekly |
| Hardware economics are hidden | High | High | Measure BOM/labor/replacement; separate Gateway and installation revenue |
| Grant claims delay or damage sales trust | Medium | Medium | Treat grants as qualification path, never guaranteed entitlement |
| Three verticals dilute the team | High | Medium | Run cohort for learning, then choose lead wedge from evidence |
| Founder remains the only technical installer/support person | High | High | Productize diagnostics/runbooks; train one field owner and partner path |

## 11. Milestone Plan

These are gated operating targets, not financial forecasts.

### July–August 2026

- Close P0 technical issues.
- Complete three vertical CM4 replays.
- Run 3–5 canaries, then the wider qualified cohort.
- Measure first-data time, support effort, telemetry coverage, actions, and willingness to pay.
- Produce the first exact-equipment installation records and customer outcome evidence.

### September–October 2026

- Convert at least five customers to paid design-partner or subscription terms.
- Select the lead wedge from evidence.
- Publish two or three permissioned case studies with measured outcomes.
- Lock Gateway BOM, assurance price, installation model, and support limits.
- Align live Stripe, contracts, data processing, support, and customer release operations.

### November 2026–January 2027

- Target 15–25 paying locations if contribution margin and support gates pass.
- Expand only high-demand verified equipment families.
- Train an installation/support partner for the lead vertical.
- Start relevant pre-approval/grant-path assessment with no eligibility promise.
- Introduce secure OTA only after signing, rollback, and fleet evidence are complete.

### First half of 2027

- Target 30–50 paying locations only if churn, support, and deployment economics remain healthy.
- Prove expansion revenue within existing customers.
- Formalize partner enablement and service boundaries.
- Evaluate Malaysia entry based on signed partner/customer demand.
- Invest in predictive/AI features that have enough trustworthy data and a demonstrated customer decision to improve.

## 12. Decisions Required from the Founders

- [ ] Confirm energy monitoring as the primary commercial wedge while retaining the other two as structured learning cohorts.
- [ ] Approve the 60-day managed design-partner model.
- [ ] Decide commitment fee versus refundable equipment deposit.
- [ ] Approve separate Gateway assurance and installation economics.
- [ ] Confirm the no-custom-code and no-unreviewed-control rules.
- [ ] Authorize the CTO launch gate to hold individual customers or verticals.
- [ ] Decide whether OTA and inbound WhatsApp maintenance mutation are disabled for the canary or hardened before it.
- [ ] Set minimum paid-conversion and support-effort thresholds for expanding beyond twenty sites.

## Conclusion

Novena has crossed the boundary from an attractive prototype into a credible pre-launch industrial product. The hardened Gateway improves the core differentiation and gives the company a realistic path to manage an installed fleet.

The commercial opportunity now depends on discipline. Novena must standardize what it supports, price the field work honestly, protect customer isolation, and use the first cohort to prove paid repeatability. If five customers can reach trustworthy first data with declining support effort and choose to pay, the company will have evidence for a focused Singapore business. If every site remains a custom engineering project, the correct response is to narrow the product—not accelerate the sales promise.
