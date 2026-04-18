# Walkthrough: Sprint 1 â€” Role-Based Access Control (RBAC)

We have successfully overhauled the Nodeflow access control system from a simple Admin/Member model to a robust, 5-tier industrial-grade RBAC system. This foundation ensures that plant managers, operators, and viewers only see and do what they are authorized to.

## ðŸ”‘ The New 5-Tier Role System

Occupying the hierarchy are five distinct roles, each with a specific purpose in an industrial setting:

| Role | Purpose | Permissions |
| :--- | :--- | :--- |
| **Owner** | Full team control + Billing | Everything + Delete Team + Subscription |
| **Admin** | High-level facility management | Device/Site/Alert management + Team Invites |
| **Manager** | Operational site management | Site/Device management + Alert logic |
| **Operator** | Day-to-day monitoring | Real-time monitoring + Acknowledge Alerts |
| **Viewer** | Read-only access | Viewing Dashboards & Reports only |

---

## ðŸ› ï¸� Technical Components

### 1. Permission Mapping
Located in `apps/teams/roles.py`, we now have a centralized map of roles to functional permissions.
- **Key Permissions:** `manage_team`, `manage_devices`, `manage_alerts`, `view_data`, `acknowledge_alerts`.

### 2. Backend Enforcement
We implemented a custom decorator and mixin to protect views:
- **Decorator:** `@require_permission('perm_name')`
- **Mixin:** `PermissionRequiredMixin`
- **Protected Views:** Alerts (Create/Update/Delete), Sites (Create/Update), Devices, and Team Management.

### 3. UI-Level Security
Templates now use the `{% has_perm %}` tag to conditionally render interface elements.
- **Buttons Hidden for Viewers:** "Add Site", "Create Rule", "Delete Team", "Invite Member".
- **Buttons Hidden for Operators:** All "Management" buttons; they only see "Acknowledge" on alerts.
- **Role Badges:** Colored pill labels in the team member list (`Owner`, `Admin`, etc.).
- **Role Reference Guide:** A dynamic guide on the team management page explaining what each role can do.

---

## ðŸš€ Verification Steps

To verify the implementation, log in and navigate to the following key pages:

### Team Management
- **URL:** `/a/[team-slug]/team/`
- **Expect:** Role badges next to member names, "Invite Team Members" form with role dropdown, and the "Role Reference Guide" at the bottom.

### Alerts Dashboard
- **URL:** `/a/[team-slug]/alerts/`
- **Expect:** Edit/Delete icons on rule cards only if you are **Manager** or higher. "CREATE RULE" button visibility controlled by role.

### Sites & Devices
- **URL:** `/a/[team-slug]/devices/sites/`
- **Expect:** "Add Site" and "Edit" links visible only to **Manager** or higher.

---

## ðŸ�› Bugfixes & Refinements
During verification, we addressed several critical items:
- **Template Errors:** Fixed a duplicated endblock in the alerts template.
- **Null Guards:** Added safe checks for `rule.site.name` to prevent crashes when a rule isn't attached to a site.
- **Auth Settings:** Corrected `allauth` configuration to ensure seamless email-only signup in the test environment.
- **Legacy Tests:** Updated all existing Pegasus tests to align with the new 5-tier role strings.

---

## Walkthrough: Sprint 2 â€” AI "Chat With Your Data"

We have successfully integrated a powerful AI assistant that can browse, analyze, and summarize your real-time IoT data. This moves Nodeflow from a simple monitoring tool to an intelligent advisor.

### ðŸ¤– Intelligent Tool Execution
The AI is no longer just a text generator. It has been built with **Function Calling** (via LiteLLM) allowing it to "reach into" the Nodeflow database:
- **`get_device_status`**: The AI can check which devices are online and their latest sensor readings.
- **`get_energy_data`**: The AI can aggregate thousands of telemetry points into clean summaries (hourly/daily).
- **`get_alerts_summary`**: The AI can audit recent issues across your facilities.

### ðŸŽ¨ Premium Chat Experience
We overhauled the chat interface to match our "Rich Aesthetics" goal:
- **Glassmorphism Header**: A blur-effect header with an integrated **Monthly Query Counter**.
- **Interactive Suggestions**: Added clickable pill-buttons for common queries like *"Analyze energy for the last 24h"* or *"Are there any anomalies?"*.
- **Live Query Status**: When the AI is fetching data, the UI now displays a subtle status indicator: `(Querying get energy data...)`.
- **Markdown & Tables**: The AI now returns structured data in clean Markdown tables for easy reading.

### ðŸ“ˆ Usage & Sustainability
To ensure cost-predictability for the SaaS model, we implemented:
- **`ChatUsage` Tracking**: Each query is logged per-team.
- **Monthly Resets**: Track usage against subscription tier limits.

### ðŸš€ Verification
1. Open **AI Chat** from the sidebar.
2. Click the suggested question: *"What is the current status of all my devices?"*.
3. Watch as the AI identifies your devices, queries their recent readings, and presents an "At a Glance" status report.

---

## Walkthrough: Sprint 3 — Write-Back / Remote Control

Nodeflow is no longer just a " Read-Only\ dashboard. We have implemented a secure, industrial-grade **Write-Back Engine** that enables remote control of PLCs and equipment directly from the web interface.

### ?? Bidirectional Control Engine
Weve integrated a sophisticated MQTT RPC (Remote Procedure Call) bridge:
- **DeviceCommand Model**: Every click is audited. We track the user who sent it, the exact payload, the transaction ID, and the outcome (Success/Failure).
- **ThingsBoard Compatibility**: Our command structure follows the 1/gateway/rpc standard, ensuring compatibility with the industrial-standard TB Gateway.
- **Asynchronous ACK**: When you send a command, Nodeflow doesnt block. It polls for a response from the edge in the background using HTMX.

### ??? Dynamic Control UI
The **Device Detail** page has been upgraded with a dedicated **Remote Controls** section:
- **Auto-Discovery**: The UI automatically detects \writable\ registers from the equipment template and renders the appropriate control (e.g., ON/OFF buttons for motors, or sliders for speed/temperature).
- **Real-Time Status**: Command buttons transform into \Sent...\ or \Success\ badges the moment the edge gateway responds.
- **Audit Trail**: A live **Command Audit Trail** table shows the history of all remote operations for that device, complete with timestamps and user-attribution.

### ??? Safety & RBAC
- **Strict Permissions**: Remote control is restricted to Manager, Admin, and Owner roles. Viewers and Operators can only monitor.
- **Visual Warnings**: Added a Safety Warning footer to remind users that local physical interlocks must always remain primary.

### ?? Verification
1. Open a **Device Detail** page (ensure a template with writable: true registers is used).
2. Click **ON** on the \Motor Enable\ control.
3. Observe the **Sent...** badge appearing.
4. Once the edge simulator (or PLC) acknowledges, the badge turns into a green **Success** check.
5. Check the **Command Audit Trail** to see your action logged for permanent record.


---

## Walkthrough: Sprint 4 — Public Shareable Links

Nodeflow now provides teams with the ability to safely share their live facility data with external stakeholders (auditors, executives, or public displays) without requiring them to create an account.

### ?? Secure & Configurable Sharing
The new **Shared Links** interface allows Managers and Admins to generate unique, tokenized URLs that bypass traditional authentication.
- **Expiry Dates**: Set a specific date and time for the link to automatically deactivate, perfect for temporary audits.
- **Password Protection**: Optionally secure links with a passphrase. External users will be greeted with a " Protected Dashboard\ prompt before they can view any data.
- **View Analytics**: Track engagement! Every successful dashboard load increments a view counter and updates the Last Viewed timestamp, giving you visibility into who is accessing your data.

### ?? Kiosk Mode for TV Displays
The public dashboard has been designed with a specific focus on unattended TV displays (e.g., in a reception area or on the factory floor).
- **Auto-Refresh**: The dashboard automatically refreshes every 60 seconds to ensure the latest data is always on screen.
- **?kiosk=1 Parameter**: Appending this to the URL entirely hides the navigation header, maximizing screen real-estate for the actual data metrics and active alerts.
- **Clean Aesthetic**: A minimal, beautiful layout showcasing the Powered by Nodeflow branding.

### ??? RBAC Integration
We ensured that Public Links adhere to the 5-tier role system.
- Viewers and Operators do not have permission to view, create, or delete shared links.
- Only Managers, Admins, and Owners have access to the **Shared Links** management console.

### ?? Verification
1. Navigate to **Shared Links** in the sidebar.
2. Click **Create Link**, name it \Reception Display\, and set a password.
3. Once created, click the **Copy** button to grab the URL.
4. Open an Incognito window and paste the URL.
5. Enter the password at the prompt.
6. Verify the dashboard loads, then try appending ?kiosk=1 to the URL.
7. Return to the management console to see the view count incremented.

---

## Walkthrough: Sprint 5 - Maintenance Ticketing

Nodeflow now includes a comprehensive, industrial-grade **Maintenance Ticketing System**. We have successfully bridged the gap between automated machine monitoring and human operational workflows.

### ⚙️ Reactive Maintenance (Automated)
Your Edge Gateways now talk directly to your service team:
- **Auto-Ticketing**: When an Alert reaches `warning` or `critical` severity, the system automatically creates a reactive `MaintenanceTicket`.
- **Smart Priority Mapping**: `Critical` alerts instantly spawn `Critical` priority tickets, ensuring no severe anomalies slip through the cracks.
- **Traceability**: Tickets permanently link back to the exact alert and telemetry reading that caused them.

### 📅 Preventive Maintenance (Scheduled)
Ditch the spreadsheets for routine servicing:
- **Procedure Templates**: Define standard operating procedures natively in the app (`TicketTemplate`) complete with estimated durations.
- **PM Schedules**: Link a template to a specific pump or chiller, and set it to recur Daily, Weekly, Monthly, or Yearly.
- **Celery Engine**: Our backend (`generate_preventive_tickets` Celery Beat task) runs silently every night. It scans for due dates, automatically spawns the relevant tickets with full procedure instructions, and safely advances the due date forward.

### 💬 Operations Collaboration UI
The UI is built for the factory floor:
- **Ticket Command Center**: A clean, tabbed interface to quickly filter between Open, In Progress, and Overdue tasks.
- **Threaded Timelines**: Deep dive into any ticket. Operators can log status changes and post threaded comments updating on parts availability or repair progress directly alongside the issue description.
- **Dashboard Visibility**: The main team "Command Center" dashboard now prominently highlights the number of active Open Tickets and Overdue PMs to facility managers at a glance.

### 🔒 RBAC Guardrails
- **Viewers/Operators**: Have full transparency to view the ticket queue and monitor repair status, but cannot create or manipulate schedules.
- **Managers+**: Empowered to assign tasks, define preventive schedules, and dictate procedure templates.

### ✅ Verification
1. Navigate to the **Maintenance** tab in the sidebar.
2. View the **Tickets** queue and test the tabbed status filters.
3. Click into a ticket to view the split-pane layout and add a comment to the timeline.
4. Go to **PM Schedules** and review the intuitive grid showing current targets and upcoming due dates.
5. Return to the main **Dashboard** to see the new Maintenance widgets populated with live counts.
7. Return to the management console to see the iew_count incremented.


---

## Walkthrough: Sprint 6 — Logic & Cloud Automations

Nodeflow now features a powerful, rule-based **Automations Engine** that can react to live telemetry streams in real-time, effectively serving as a centralized, cloud-hosted PLC.

### 🧠 Advanced Trigger Conditions
We expanded beyond simple threshold alerts into a multi-variable logic engine:
- **AND / OR Evaluators**: Each automation can require *all* conditions to be met, or trigger if *any* single condition is met.
- **Sustained Durations (Redis Tracking)**: You can now configure rules like *"If Temp > 100°C FOR 60 seconds"*. The engine uses Redis caches to track sustained states across telemetry payloads before firing off actions, preventing false positives.
- **Dynamic Operators**: Supports strictly mathematical operators (`>`, `<=`, `==`) and boolean state checks (`Is True`, `Is False`).

### ⚡ Automated Actions Array
When conditions are satisfied, Nodeflow immediately takes action directly at the execution edge or informs other business systems:
- **Send RPC Commands**: Automatically write back to PLC registers or gateways (e.g., *Shut off Pump 1 if Tank Level < 10%*).
- **Fire Webhooks**: Post JSON payloads out to third-party APIs (like Zapier, Slack, or external CRMs).
- **Email Notifications**: Alert maintenance teams dynamically.
- **Cooldown Periods**: Automations feature customizable *Cooldowns* (e.g., lock out for 15 minutes after firing) to prevent bouncing systems from spamming commands or webhooks.

### 🧩 The IFTTT-Style Builder UI
We designed a clean, user-friendly builder using Django Formsets that makes creating logic easy for non-programmers:
- **Split Configuration**: Defines the IF blocks dynamically with drop-downs pulling strictly from the team's available IoT devices.
- **Visual Indicators**: Displays the current State (Active/Paused) alongside a count of linked logic blocks on the dashboard.

### 🛡️ Deep Auditing
- **Dedicated Audit Logs**: Every automation execution is permanently recorded in `AutomationLog`, detailing the precise timestamp, the overall status (`success`, `partial`, `failed`), and output debug lines indicating exactly which webhooks or RPCs succeeded or failed.
- **Safety First**: As always, `manage_automations` is strictly restricted to Admins and Owners. We also injected a disclaimer banner reminding operators that cloud automations should not override local hardwired interlocks.

### ✅ Verification
1. Navigate to the **Automations** tab in the sidebar.
2. Click **Create Automation** and use the unified builder to set up an Over-Temperature Shutoff.
3. In the **Conditions** block, select a device, choose the `temp` key, operator `>` and threshold `100` with a 15-second duration.
4. In the **Actions** block, select Send Command, choose the device and type `turn_off` for the command key.
5. Save the automation. Observe it on the list view.
6. Check the **Audit Logs** tab natively inside the application after simulating telemetry data to see the engine log its execution.

---

## Phase 2 Sprint 7A: Dashboard Command Center Overhaul

Developed a premium "Command Center" dashboard that transitions Nodeflow from a basic monitoring tool into a professional operations control room.

### Key Work Completed

*   **Real Data Ingestion:** Replaced all hardcoded sample chart data with real hourly energy aggregates queried from TimescaleDB (last 24h).
*   **Enriched backend logic:** Updated `apps/web/views.py` to calculate device health (online/offline), gateway status, active alerts, and automation counts.
*   **Redis Caching:** Implemented 60-second Redis caching for heavy dashboard queries to ensure sub-second page loads.
*   **Premium KPI Strip:** Designed a 5-card operational strip featuring Energy, Active Alerts, Fleet Health, Maintenance, and Automations.
*   **High-Visibility Alert Feed:** Added a live-updating feed showing the 5 most recent triggered alerts with severity badges and direct navigation links.
*   **Device Fleet Grid:** Integrated a real-time status grid for the top 8 devices, showing last readings and connectivity dots.
*   **Quick Actions Panel:** Centralized administrative shortcuts for adding hardware, creating rules, and viewing reports.
*   **HTMX Auto-Refresh:** Implemented a 60-second HTMX auto-trigger that refreshes live metrics and feeds without a full page reload.
*   **Stability & Fixes:** Resolved a regression where `request.team.slug` access in the navigation caused errors in team-agnostic views (e.g., user profile).

### Technical Deep Dive

1.  **View Layer:** `team_home` now performs a unified aggregate query for the fleet energy profile.
2.  **Template Layer:** Deeply semantic HTML5 with Tailwind CSS + DaisyUI. Used Alpine.js for interactive elements and HTMX for the background refresh loop.
3.  **Stability:** Fixed `notifications_dropdown.html` to gracefully handle cases where `request.team` is missing.

### Verification Results

*   **Automated Tests:** Ran `apps.web.tests` — all 29 tests passed (regression fix verified).
*   **Manual Verification:** Verified dashboard layout, KPI accuracy, and HTMX refresh loop on local development server.

---

## Phase 2 Sprint 7B: Multi-Page Marketing Website

Transformed the single-page landing page into a comprehensive, professional multi-page marketing site designed for high conversion and market trust.

### Key Work Completed

*   **Sticky Premium Navigation:** Overhauled `top_nav.html` with a scroll-responsive sticky design, multi-page link structure, and a mobile drawer.
*   **Hyper-Realistic Visuals:** Generated and deployed a 3D-style dashboard hero image (`static/images/marketing_hero.png`) to showcase the platform's power.
*   **Landing Page Redesign:** Completely rewrote `landing_page.html` with sections for social proof, problem/solution, core features, and an AI intelligence spotlight.
*   **Expansion Architecture:** Created four new dedicated marketing pages:
    *   `/product/`: Highlighting the 6 core pillars of the Nodeflow platform.
    *   `/solutions/`: Vertical-specific case studies for Energy, Cold Chain, and Factory floors.
    *   `/pricing/`: Subscription tiers with a detailed feature comparison matrix and FAQ.
    *   `/about/`: Company mission, values, and an industrial-grade contact system.
*   **Wagtail Resources Hub:** Built professional templates for the Wagtail-powered Resources/Blog hub, ensuring the documentation and insights feel native to the premium brand.
*   **Modern Footer:** Implemented a multi-column professional footer with links across product, company, and resources.

### Technical Deep Dive

1.  **Frontend:** Integrated **AOS.js (Animate On Scroll)** for smooth slide-up and fade animations. Use Alpine.js for interactive dropdowns and mobile menu state.
2.  **CMS:** Connected Wagtail models to custom templates using semantic HTML5 and `prose` classes for readable documentation.

### Verification Results

*   **URL Routing:** All new routes (`/product/`, `/pricing/`, etc.) verified working.
*   **Responsive Design:** Tested sticky nav and mobile drawer across desktop and mobile breakpoints.
*   **Asset Loading:** Verified hyper-realistic hero image loads correctly via static files.

---

## Phase 2 Sprint 7C: Onboarding Polish + Architecture Refinements

Finalized the production readiness of Nodeflow's core workflows, ensuring robust security, polished user experience, and automated background maintenance.

### Key Work Completed

*   **Onboarding RBAC Hardening:** Added granular `@require_permission` checks across all `apps/onboarding/` views. Provisioning logic is now restricted to `manager` and `admin` roles, preventing unauthorized infrastructure modification.
*   **Celebratory Onboarding Completion:** Completely redesigned `onboarding/complete.html`. Added a success celebration card, a configuration summary, and actionable next steps for MQTT gateway integration.
*   **Automation UX Polish:** Enhanced the `automation_form.html` with Alpine.js to provide conditional field visibility. Configuration fields for Commands, Webhooks, and Notifications now only appear when their respective action types are selected, significantly reducing cognitive load.
*   **Preventive Maintenance Automation:** Configured the `generate_preventive_tickets` task in `CELERY_BEAT_SCHEDULE` to run daily. Nodeflow will now automatically generate PM orders based on defined schedules without manual intervention.
*   **Foundation Reliability:** Verified the entire platform stability with a clean test suite run, resolving edge-case template rendering issues.

### Technical Deep Dive

1.  **Backend:** Secured the onboarding URL patterns by switching from basic team login decorators to Nodeflow's specific RBAC permission decorators.
2.  **UI/UX:** Used **Alpine.js `x-model` and `x-show`** to create a dynamic, single-page-app feel for complex multi-action forms.
3.  **Operations:** Integrated Celery Beat for system-wide background task orchestration.

### Phase 2 Verified Status: ✅ MARKET READY

All 18 major features across Sprints 1-6 are now polished, secured, and wrapped in a premium, multi-page SaaS shell. Nodeflow is ready for real-world pilot deployments.
