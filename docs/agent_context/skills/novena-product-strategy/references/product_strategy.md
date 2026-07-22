# Product Strategy Reference

## Positioning
Novena Platform is an AI-powered industrial IoT SaaS platform for industrial and commercial SMEs in Singapore and ASEAN.

Simple framing:

- Plug-and-play industrial monitoring.
- Managed, standardized gateway hardware plus powerful cloud software.
- Zero-code setup for teams that cannot afford custom enterprise IIoT projects.

The repeatable product unit is: managed Novena Gateway + exact-device verified template + vertical outcome pack + safe installation method + remote support. Plug-and-play means no software engineering after approved physical installation; it does not mean untrained customers wire live industrial equipment.

## Primary Vertical
Energy efficiency and monitoring is the current focus because it has clear ROI, rising cost pressure, and strong fit with Singapore and ASEAN digitization/grant narratives.

Future verticals:

- Cold chain and food safety.
- Predictive maintenance for facilities.
- Multi-site facilities operations.

The July 2026 design-partner cohort may test all three profiles, but qualification quality takes priority over an equal split. Choose the lead commercial wedge after measuring paid conversion, time to first data, installation/support effort, weekly use, and expansion potential.

## Pricing Direction
- Starter: low-friction entry, limited users/gateways/retention.
- Business: core SME plan, RBAC, more gateways, longer retention, preventive maintenance, AI chat.
- Enterprise: custom gateways/retention, API/SSO/white-label/dedicated support.

Feature gating should nudge real businesses toward Business without making Starter feel broken.

Gateway provisioning/burn-in, physical installation, third-party sensors/accessories, and field service have real costs and should not be silently bundled into low-price SaaS. Validate a separate Gateway assurance model and transparent installation charge during the design-partner cohort.

## Product Priorities
1. Close cross-system identity, activation, tenant-isolation, and OTA trust blockers.
2. Commit a reproducible Hub/Gateway release and complete current CM4 hardware replays.
3. Run a 3-5 customer technical canary before expanding to the planned 20-customer cohort.
4. Prove exact-device templates, time to first value, support burden, and paid conversion.
5. Finish production billing/webhook enforcement, customer setup documentation, and mobile/tablet field polish.

AI and broad protocol/template expansion are not launch dependencies. Prioritize trustworthy telemetry, clear freshness, useful alerts, and operator action.

## Wording Rules
- Prefer concrete status over abstract system language.
- Explain freshness and connectivity clearly.
- Avoid exposing internal implementation terms such as Redis, Celery, or Channels in customer UI.
- Use Gateway online - device offline when the edge is reachable but field telemetry is stale.
