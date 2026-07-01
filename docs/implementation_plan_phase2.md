# Implementation Plan — Phase 2: Dashboard, Marketing Site & Polish

> **Date:** April 18, 2026  
> **Depends on:** Sprints 1-6 (all complete)  
> **Context:** Edge gateway exists in separate repo (owner-managed). Focus here: make Novena Hub world-class.

---

## Workstream 1: Dashboard Command Center Overhaul

The dashboard is where users spend 80% of their time. Currently it has good bones — KPI cards, a fleet chart, site navigator, and operations feed — but it needs to feel like a **premium operations control room**.

### Current State

- Energy (24h) KPI card — uses hardcoded sample chart data points
- Nodes count (sites/devices) — static numbers
- Maintenance card (open tickets, overdue PMs) — functional
- Fleet Energy chart — fake data points with only the last one real
- Site Navigator — basic list
- Operations Feed — filterable activity log

### Proposed Changes

#### [MODIFY] `apps/web/views.py`
Enrich the `team_home` context with:
- **Active alerts** count + most recent 3 critical/warning alerts (with direct links)
- **Device fleet health** — counts of online, offline, never-seen devices
- **Active automations** count
- **Real hourly energy data** for the fleet chart (last 24h from TimescaleDB, 1-point-per-hour)
- **Gateway health** — online vs offline gateways
- Cache all heavy queries in Redis (60s TTL) to keep page load fast

#### [MODIFY] `templates/web/app_home.html`
Complete redesign of the dashboard layout:

**Row 1 — KPI Strip (5 mini cards)**

| Energy (24h) | Active Alerts | Devices Online | Open Tickets | Automations |

Each with icon, large number, subtle trend indicator, and clickable link to the relevant page.

**Row 2 — Main Content (2 columns)**
- **Left (2/3):** Fleet Energy Chart with REAL hourly data from TimescaleDB. Add device-level breakdown toggle. HTMX auto-refresh every 60s.
- **Right (1/3):** Live Alert Feed — the 5 most recent triggered alerts with severity badges, device name, timestamp, and "View" link. Replaces generic operations feed.

**Row 3 — Bottom (3 columns)**
- **Col 1:** Site Navigator (keep, polish)
- **Col 2:** Device Fleet Grid — top 8 devices as mini cards showing name, status dot (green/red), last reading, last seen timestamp
- **Col 3:** Quick Actions panel — "Add Hardware", "Create Alert Rule", "Create Automation", "View Reports"

---

## Workstream 2: Multi-Page Marketing Website

### Current State

Single `landing_page.html` with:
- Hero section with placeholder mockup (spinning loader, no real content)
- Fake company logos (SOLARCO, INDUS, etc.)
- 2 feature spotlights with placeholder icons (no images)
- Pricing section (Starter/Pro/Business)
- CTA footer
- Very basic `top_nav.html` with only "Blog" link
- Very basic `footer.html` (just copyright + Pegasus attribution)

### Proposed Architecture

Transform from a single-page template into a multi-section marketing site:

```
Marketing Site Structure:
├── / (Home) — Hero, social proof, feature highlights, pricing CTA
├── /#features — Scroll anchor (on home page)
├── /#pricing — Scroll anchor (on home page)
├── /product/ — Detailed product page (all features explained)
├── /solutions/ — Use cases page (Energy, Cold Chain, Factory)
├── /pricing/ — Dedicated pricing page with FAQ
├── /resources/ — Wagtail-powered (Blog, Docs, FAQ)
│   ├── /content/blog/ — Blog index (Wagtail)
│   └── /content/docs/ — Setup guides, API docs (Wagtail)
└── /about/ — Company story, team, contact
```

### Proposed Changes

#### [MODIFY] `templates/web/components/top_nav.html`
Replace current basic nav with a premium sticky navigation bar:
- **Left:** Novena logo/wordmark
- **Center:** Product | Solutions | Pricing | Resources (dropdown with Blog, Docs, FAQ)
- **Right:** Sign In | **Get Started** (primary CTA button)
- **Behavior:** Transparent on hero, becomes solid white/dark with shadow on scroll (Alpine.js)
- **Mobile:** Hamburger menu with slide-out drawer

#### [NEW] `templates/web/product.html`
Full product page showcasing all 6 sprint deliverables as premium feature sections:
- Real-time Monitoring & Dashboards
- AI-Powered Intelligence
- Remote Control (Write-Back)
- Logic & Automations
- Maintenance Management
- Shared Links & Kiosk Mode

Each section: heading + description + feature image/screenshot + bullet points

#### [NEW] `templates/web/solutions.html`
Three solution cards/tabs:
- **Energy Monitoring** — submeter tracking, peak shaving, carbon reporting
- **Cold Chain** — temperature compliance, SFA requirements, spoilage prevention
- **Factory / OEM** — motor health, VFD monitoring, downtime tracking

#### [NEW] `templates/web/pricing.html`
Dedicated pricing page with:
- Same 3-tier pricing cards (from current landing page, refined)
- Feature comparison table (full matrix)
- FAQ accordion (common pricing questions)
- "Talk to Sales" CTA for Enterprise

#### [NEW] `templates/web/about.html`
Company page:
- Mission statement, founding story, Singapore-first positioning
- Contact form or email link

#### [MODIFY] `templates/web/landing_page.html`
Overhaul the home page:
- **Hero:** Real dashboard screenshot (generated image) instead of spinning placeholder
- **Social proof:** Replace fake logos with "Trusted by X+ facilities" counter
- **Feature grid:** 6 cards (one per sprint feature) with icons and short descriptions, linking to /product/
- **How it works:** 3-step visual (Connect → Monitor → Automate)
- **Pricing preview:** 3 tiers with "See all features →" link to /pricing/
- **CTA:** "Book a Demo" + "Start Free Trial"

#### [MODIFY] `templates/web/components/footer.html`
Professional multi-column footer:
- **Col 1:** Novena logo + tagline + social links
- **Col 2:** Product links (Features, Pricing, Integrations)
- **Col 3:** Resources links (Blog, Docs, FAQ, API)
- **Col 4:** Company links (About, Contact, Careers)
- **Bottom bar:** Copyright + Privacy Policy + Terms of Service

#### [MODIFY] `apps/web/urls.py`
Add routes: `/product/`, `/solutions/`, `/pricing/`, `/about/`

---

## Workstream 3: Onboarding Flow Polish

### Current State
- 4-step wizard: Site → Gateway → Device → Alert
- Setup wizard for existing customers (select site → connectivity → gateway → device)
- Works but hasn't been verified against newer features (RBAC, automations, maintenance)

### Proposed Changes

#### [MODIFY] `apps/onboarding/views.py`
- Add RBAC check: only `manage_devices` permission can access onboarding
- On `complete` step: offer quick links to "Create an Automation" and "Set up Maintenance Schedule"
- After completing onboarding with a template that has alert presets, show summaries

#### [MODIFY] `templates/onboarding/complete.html`
Redesign the completion page:
- Success animation
- Summary of what was created (site name, gateway SN, device name, alert rules)
- Quick action cards: "Go to Dashboard" | "Create Automation Rule" | "Set Up PM Schedule" | "Add Another Device"

---

## Workstream 4: Quick Architecture Refinements

#### [MODIFY] `templates/automations/automation_form.html`
Add Alpine.js `x-show` directives to action fields:
- Show command fields only when `action_type == 'send_command'`
- Show webhook_url only when `action_type == 'webhook'`
- Show notify_emails only when `action_type == 'notify_email'`

#### [MODIFY] `novena_hub/settings.py`
Add `generate_preventive_tickets` to `CELERY_BEAT_SCHEDULE`

#### [MODIFY] `templates/web/app_home.html`
Fix stray ` stone` text at line 245 (leftover from previous edit)

---

## Execution Order

| Sprint | Workstream | Effort | User Impact |
|--------|-----------|--------|-------------|
| **7A** | Dashboard Command Center Overhaul | 2-3 days | Highest — where users live |
| **7B** | Multi-Page Marketing Website | 3-4 days | Customer-facing first impression |
| **7C** | Onboarding Polish + Arch Refinements | 1-2 days | Cleanup & discoverability |

---

## Open Questions

> [!IMPORTANT]
> 1. **Dashboard screenshots for marketing site:** Should I generate mock dashboard images for the hero, or wait for real screenshots after the dashboard overhaul?
>
> 2. **Wagtail Resources:** Should I build templates for a Docs/Blog hub, or just hook up the nav links for you to populate content in `/cms/`?
>
> 3. **Execution order:** Dashboard first → Marketing site → Polish. Good?
