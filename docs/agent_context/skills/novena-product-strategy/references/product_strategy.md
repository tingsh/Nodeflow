# Product Strategy Reference

## Positioning
Novena Platform is an AI-powered industrial IoT SaaS platform for industrial and commercial SMEs in Singapore and ASEAN.

Simple framing:

- Plug-and-play industrial monitoring.
- Standardized gateway hardware plus powerful cloud software.
- Zero-code setup for teams that cannot afford custom enterprise IIoT projects.

## Primary Vertical
Energy efficiency and monitoring is the current focus because it has clear ROI, rising cost pressure, and strong fit with Singapore and ASEAN digitization/grant narratives.

Future verticals:

- Cold chain and food safety.
- Predictive maintenance for facilities.
- Multi-site facilities operations.

## Pricing Direction
- Starter: low-friction entry, limited users/gateways/retention.
- Business: core SME plan, RBAC, more gateways, longer retention, preventive maintenance, AI chat.
- Enterprise: custom gateways/retention, API/SSO/white-label/dedicated support.

Feature gating should nudge real businesses toward Business without making Starter feel broken.

## Product Priorities
1. Hardware-test reliability and clear trust signals.
2. Production-like WSL and deployment alignment.
3. Billing/tier enforcement.
4. Customer setup docs and operational documentation.
5. Mobile/tablet polish for field use.

## Wording Rules
- Prefer concrete status over abstract system language.
- Explain freshness and connectivity clearly.
- Avoid exposing internal implementation terms such as Redis, Celery, or Channels in customer UI.
- Use Gateway online - device offline when the edge is reachable but field telemetry is stale.
