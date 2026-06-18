# Skill: Project Status & Roadmap

## Metadata
- **ID:** 07_project_status
- **Description:** Living record of the current build state, completed features, and high-priority roadmap items.
- **Scope:** Use this skill at the start of every session to understand "where we are" and at the end of every session to update "what we did."

---

## 1. Current Stage
- **Phase:** Pre-Launch / Release Candidate
- **Status:** 100% of core features, advanced features (AI, Automation), and marketing tools completed. Project is in final polishing phase.

## 2. What's Built (✅)

### Nodeflow Cloud (Backend & Platform)
- **Multi-Tenancy & Security:** Pegasus-based teams, hardened RBAC (5 roles), and Shareable Public Links with Expiring Tokens.
- **Zero-Touch Onboarding:** 4-step wizard, hardware auto-detection, "Plug Claim Play" logic, and Gateway Discovery API.
- **Device Management:** Intelligent Port Grid, fuzzy matching for device templates, progressive disclosure of raw register maps, and live connection testing.
- **Optimized Telemetry Engine:** MQTT ingestion to TimescaleDB, enhanced by Redis buffering, Celery Beat task flushers, and WebSockets with plan-gated latency.
- **Automation & Alerts:** "Cloud PLC" automation engine, Alert Presets, threshold rules, and remote control write-back logic.
- **AI & Insights:** "AI Chat With Your Data" using litellm function calling.
- **Operations & Maintenance:** Reactive and Preventive Maintenance Ticketing Workflow.
- **UI & UX Polish:** Premium 'Dark Energy' Bento-style Auto-Dashboards, Fleet Command Center with geographical maps, and Unified Hub Navigation.
- **Marketing & Content:** Wagtail CMS integration, multi-page marketing site overhaul, and pre-launch product blueprint.

### Nodeflow Edge (Gateway Daemon)
- **Provisioning:** Initialization of Nodeflow Edge with Plug Claim Play feature support.
- **Offline Resilience:** SQLite offline buffering with throttled replay to handle intermittent connectivity.
- **Bidirectional RPC:** Multithreaded RPC handler for real-time live reads and remote commands.
- **Network Stability:** Multi-WAN network watchdog implementation.
- **Firmware Management:** Zero-Downtime Blue/Green OTA Firmware Update mechanism.

## 3. High-Priority Roadmap (❌)
*Items are in order of execution priority.*

1. **Launch Preparation:** Comprehensive load testing, security auditing, and final bug bashes.
2. **Billing & Tiers:** Finalize Stripe integration to enforce strict subscription limits and plan-gated features (e.g., websocket latency limits).
3. **User Documentation:** Complete the public-facing knowledge base and API documentation for end-users.
4. **Mobile Optimization:** Continued polish for "Mobile Pass" to ensure all advanced dashboards are fully responsive for tablet/mobile.

## 4. Current Sprint Goal
**Focus:** Final launch preparations, bug fixing, and platform stabilization across both cloud and edge environments.

## 5. Recent Activity Log
- **2026-06-08:** Executed Phase 2. Created standard register maps template fixtures. Built Auto-Dashboard Widget engine. Implemented Command Center map mockup. Created Zero-Downtime Blue/Green OTA Update mechanism across cloud and edge.
- **2026-06-10:** Completed Sprint optimizations: Wagtail CMS marketing site, AI Chat with Data, shareable links, and ticketing workflows. Edge offline buffering and multi-WAN watchdog deployed.
- **2026-06-12:** Completed Device Template Onboarding feature. Implemented progressive disclosure for raw register maps, and a Live Connection Test module directly within the quick-add modal. Fixed legacy view test mocks and registered device signals.
- **2026-06-12 (Later):** Conducted a holistic codebase review of Nodeflow Cloud and Nodeflow Edge. Updated project status to reflect massive progress across all 5 sprints and 4 phases, graduating the project status to Pre-Launch.
- **2026-06-13:** Executed pre-launch hardening implementation plan (Phases 1-4). Hardened edge security (daemon runs as unprivileged 'nodeflow' user), locked down production settings (HSTS, ALLOWED_HOSTS, Mailgun), updated Stripe pricing metadata & UI with direct checkout and offline simulation, and enforced dynamic application-level data retention (7, 30, 90-day limits) on telemetry API, dashboard views, and CSV exports. Created test suites for alerts and telemetry with 100% pass rate.
- **2026-06-16:** Finalized SaaS pricing strategy to use "Feature-Gating" Tripwires. Updated `06_business_context.md` with new Starter ($99), Business ($399), and Enterprise ($699) tiers to naturally funnel SME clients. Generated comprehensive 5-year Investor Analysis and TAM projection against Carro.
- **2026-06-16 (Later):** Set up and synced real Stripe products (Starter, Business, Enterprise) to local `.env` and `metadata.py`. Revamped the UI/UX of the subscription upgrade page with premium dark-mode aesthetics, glowing gradients, and unconstrained max-width containers. Tested local webhook forwarding using Stripe CLI.
- **2026-06-16 (Even Later):** Fixed HTMX interception bug with the "Manage billing" button pointing to Stripe Customer Portal. Improved the "Active Subscription" UI by exposing the user's default payment method card details and adding interactive visual progress bars for Gateway and Device usage limits based on their active Stripe Product.
- **2026-06-18:** Upgraded alert notifications engine to use Amazon SES via django-anymail and direct Meta WhatsApp Graph API. Implemented targeted notification dispatch (recipients selection via HTMX search dropdown and Alpine.js badges). Added view-level model validation to enforce selecting recipients when notifications are active. Refactored dispatches to run asynchronously as Celery tasks (`dispatch_alert_email_task` and `dispatch_alert_whatsapp_task`). Created full automated pytest suites verifying both targeted dispatches, Meta API requests mocking, and search HTMX endpoint permissions. Improved search matching to query the username field and added a "No members found" visual fallback message to the partial search results template. Fixed Django Debug Toolbar (DjDT) routing conflict where catch-all Wagtail URL patterns shadowed DjDT routes, causing 404 overlay errors during AJAX/HTMX searches.
- **2026-06-18 (Later):** Overhauled the Team application architecture. Moved team setup directly into the user signup flow (`TeamSignupForm`) requiring a company name upfront to eliminate auto-generated team names. Cleaned up global navigation by removing the legacy sidebar team switcher and consolidating Account, Team Settings, Billing, and Team Switching into the top-right user profile dropdown. Extended member management to expose the `CustomUser.phone_number` field so users can configure their WhatsApp numbers directly within the Team Settings view. Completely rewrote all team management templates (`manage_team.html`, `list_teams.html`, `team_membership_details.html`, `team_invitations.html`) discarding legacy Pegasus CSS in favor of premium Tailwind/DaisyUI components. Fixed several edge cases including `IntegrityError` crashes on duplicate invitation acceptance, `Team.email` property crashing when no admin is present, and API inconsistencies in default role assignment (`ROLE_OWNER` instead of `admin`).
- **2026-06-18 (Later - Profile & Custom Fields Polish):** Redesigned the user profile dashboard (`profile.html` and its components) using modern Tailwind CSS and DaisyUI, replacing legacy Bulma-based Pegasus styling. Implemented an Alpine.js-powered settings sidebar selector that persists the active tab across page reloads using `localStorage`. Added `job_title` and `department` fields to the `CustomUser` model to capture professional roles within the enterprise IoT team structure, generated and executed the database migrations, and exposed these fields on the profile settings forms. Redesigned the Two-Factor Authentication, Linked Accounts, and API Credentials modules with responsive components and secure confirmation alerts.
- **2026-06-18 (Later - Dropdown Navigation Upgrade):** Upgraded the global user profile navigation dropdown (`top_nav.html`) to include a personalized user identity header card (with avatar, display name, and email), active team role badge context (e.g. Owner/Admin/Viewer), and quick links to core resources (Documentation, Help Center/FAQ) to improve context awareness when navigating settings inside the application.
- **2026-06-18 (Even Later - Contact Support Modal):** Added a global "Contact Support" ticket dispatch system. Built an HTMX-powered DaisyUI modal (`contact-support-modal` in `app_base.html`) allowing users to compose technical, billing, or operational tickets. Created the `contact_support` view in the `support` app (`apps/support/views.py`) that handles category selection, validates inputs, and automatically dispatches support emails to the configured support address (`PROJECT_METADATA["CONTACT_EMAIL"]`). Built the success feedback template (`contact_success.html`) displaying confirmation checks and operational SLA expectations.
- **2026-06-18 (Alert System Hardening):** Hardened the alert and notification engine. Implemented cooldown logic hardening to include `"active"` and `"acknowledged"` states, preventing spam. Added duration-based triggers with database checks over TimescaleDB telemetry historical windows (and preceding points fallback). Added automatic resolution logic to mark alerts resolved and send green-styled email/WhatsApp notifications. Integrated asynchronous webhooks through a Celery task (`dispatch_alert_webhook_task`). Wrote a comprehensive unit test suite in `apps/alerts/tests.py` covering all seven improvements, with 100% test pass rates.



