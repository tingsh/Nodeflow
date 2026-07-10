from django.db import migrations


def block(block_type, value):
    return {"type": block_type, "value": value}


HOME_BODY = [
    block("metric_band", {
        "tagline": "Built for first deployments",
        "title": "A pilot should prove operational value quickly, without becoming a custom integration project.",
        "metrics": [
            {"value": "1", "label": "edge gateway", "detail": "Start with one site or equipment group."},
            {"value": "3-5", "label": "assets in pilot", "detail": "Meters, PLCs, sensors, chillers, pumps, or inverters."},
            {"value": "30", "label": "day review", "detail": "Use the first month to validate savings, alerts, and workflows."},
            {"value": "0", "label": "code for operators", "detail": "Templates, dashboards, and alerts are configured in Novena Hub."},
        ],
    }),
    block("process", {
        "tagline": "How Novena works",
        "title": "From field equipment to decisions your team can act on.",
        "steps": [
            {"step": "01", "title": "Connect the gateway", "description": "Deploy Novena Gateway beside your equipment and connect meters, PLCs, sensors, or existing industrial networks."},
            {"step": "02", "title": "Model the site", "description": "Create sites, devices, templates, thresholds, and dashboards that match the way your team talks about operations."},
            {"step": "03", "title": "Operate from the cloud", "description": "Monitor live status, investigate trends, receive alerts, ask AI questions, and trigger maintenance or automation workflows."},
        ],
    }),
    block("platform_capabilities", {
        "tagline": "Horizontal platform",
        "title": "Core industrial IoT primitives that adapt across verticals.",
        "intro": "Novena is not a single-purpose dashboard. The same gateway, data model, alerting, AI, and workflow layer can support energy, cold chain, production, and facilities operations.",
        "capabilities": [
            {"anchor_id": "gateway", "icon": "fa-network-wired", "title": "Gateway-led onboarding", "description": "Bring industrial equipment online through a managed edge gateway instead of custom one-off data plumbing.", "proof": "Designed for SME deployments"},
            {"anchor_id": "monitoring", "icon": "fa-chart-line", "title": "Live operational visibility", "description": "Give managers and technicians shared dashboards for site health, telemetry freshness, trends, and exceptions.", "proof": "Status, trends, and alerts together"},
            {"anchor_id": "ai", "icon": "fa-robot", "title": "AI-assisted investigation", "description": "Ask plain-language questions about energy use, alerts, anomalies, and equipment behavior without exporting spreadsheets.", "proof": "Useful for lean teams"},
            {"anchor_id": "automation", "icon": "fa-diagram-project", "title": "Alerts and workflows", "description": "Turn telemetry into notifications, maintenance tickets, and automation actions with audit trails.", "proof": "Moves from monitor to action"},
            {"anchor_id": "maintenance", "icon": "fa-screwdriver-wrench", "title": "Maintenance context", "description": "Tie alerts and run-hour data to tickets so teams know what changed, who owns it, and what happened next.", "proof": "Built for daily operations"},
            {"anchor_id": "control", "icon": "fa-shield-halved", "title": "Controlled remote actions", "description": "Support permissioned commands and setpoint changes where the customer has approved the safety model.", "proof": "RBAC and audit-first"},
        ],
    }),
    block("vertical_solution_cards", {
        "tagline": "Vertical solutions",
        "title": "Start with one operational problem. Keep the same platform as you expand.",
        "intro": "Each vertical uses the same Novena core, then adds templates, metrics, alerts, and workflows for the environment.",
        "solutions": [
            {"anchor_id": "energy", "icon": "fa-bolt", "vertical": "Energy", "title": "Energy monitoring and peak visibility", "pain": "Rising bills and demand charges are hard to explain when meters and equipment data are disconnected.", "outcome": "Track load, compare sites, detect abnormal consumption, and prepare grant or savings conversations with cleaner evidence.", "features": ["Submetering dashboards", "Peak alerts", "Solar and load comparison"], "cta_text": "Explore energy", "cta_url": "/solutions/#energy"},
            {"anchor_id": "cold-chain", "icon": "fa-temperature-low", "vertical": "Cold chain", "title": "Temperature compliance and stock protection", "pain": "Manual logs and late alerts expose teams to spoilage, compliance gaps, and preventable losses.", "outcome": "Monitor temperature, door events, compressor health, and escalation workflows from one operational view.", "features": ["Temperature trends", "WhatsApp-ready alerts", "Daily compliance summaries"], "cta_text": "Explore cold chain", "cta_url": "/solutions/#cold-chain"},
            {"anchor_id": "manufacturing", "icon": "fa-industry", "vertical": "Manufacturing", "title": "Machine visibility for factory teams", "pain": "Run-hours, faults, and production context often live inside machines until someone manually checks them.", "outcome": "Connect PLCs, VFDs, and meters to shared dashboards and maintenance workflows.", "features": ["PLC and VFD monitoring", "Run-hour based work", "Fault history"], "cta_text": "Explore manufacturing", "cta_url": "/solutions/#manufacturing"},
            {"anchor_id": "facilities", "icon": "fa-building", "vertical": "Facilities", "title": "Multi-site facilities operations", "pain": "Facility teams need to coordinate HVAC, utilities, and equipment health across sites without extra headcount.", "outcome": "Give managers a cross-site view of uptime, energy, comfort, and open actions.", "features": ["Site health rollups", "Shared dashboards", "Escalation workflows"], "cta_text": "Explore facilities", "cta_url": "/solutions/#facilities"},
        ],
    }),
    block("proof_strip", {
        "tagline": "Trust posture",
        "title": "Credible for early pilots, designed for production operations.",
        "intro": "The public site should not overclaim enterprise maturity. Novena earns trust by being clear about the pilot path, the hardware boundary, and the operating workflows it supports.",
        "proof_points": [
            {"label": "Deployment", "metric": "Pilot-first", "metric_label": "start small, expand by site", "title": "Start where ROI is visible", "body": "Energy, cold chain, and equipment uptime are concrete enough for operators to evaluate quickly."},
            {"label": "Architecture", "metric": "Edge + cloud", "metric_label": "local gateway, cloud workflows", "title": "Built for real equipment", "body": "Novena separates field connectivity from cloud operations so unstable sites can still be managed coherently."},
            {"label": "Users", "metric": "No-code", "metric_label": "for managers and technicians", "title": "Readable by non-developers", "body": "Buyer-facing surfaces explain status, freshness, alerts, and actions without exposing internal infrastructure terms."},
            {"label": "Expansion", "metric": "Horizontal", "metric_label": "one core, many verticals", "title": "Reusable operating model", "body": "The same telemetry, alert, AI, and maintenance primitives adapt as customers add more sites and use cases."},
        ],
    }),
    block("final_cta", {
        "title": "See Novena on your equipment",
        "subtitle": "Book a practical walkthrough for one site, one gateway, and a measurable pilot outcome.",
        "primary_cta_text": "Book a demo",
        "primary_cta_url": "/about/#contact",
        "secondary_cta_text": "See pricing",
        "secondary_cta_url": "/pricing/",
    }),
]


PRODUCT_BODY = [
    block("product_visual", {
        "tagline": "Platform view",
        "title": "A product surface your operators can understand at a glance.",
        "subtitle": "The dashboard visual is rendered from Novena UI patterns with representative telemetry, not customer data. It shows how site health, energy trends, alerts, and AI summaries sit together.",
        "visual_type": "operations",
        "bg_color": "white",
    }),
    block("platform_capabilities", HOME_BODY[2]["value"]),
    block("process", {
        "tagline": "Implementation model",
        "title": "Deploy the platform in layers, not as a risky big-bang project.",
        "steps": [
            {"step": "Layer 1", "title": "Connectivity", "description": "Bring selected equipment online with Novena Gateway and confirm telemetry freshness."},
            {"step": "Layer 2", "title": "Visibility", "description": "Create dashboards, alerts, and site views for the assets that matter most."},
            {"step": "Layer 3", "title": "Action", "description": "Add AI investigation, maintenance tickets, automations, and controlled commands where appropriate."},
        ],
    }),
    block("proof_strip", {
        "tagline": "Platform principles",
        "title": "Operational software should be calm, clear, and accountable.",
        "intro": "Novena is designed for teams who need to know what is happening now, whether the data is fresh, and what action should happen next.",
        "proof_points": [
            {"label": "Freshness", "title": "Status includes context", "body": "Pages should say whether data is live, delayed, or stale instead of showing vague green lights.", "metric": "Live", "metric_label": "updated seconds ago"},
            {"label": "Control", "title": "Actions need audit trails", "body": "Remote actions are permissioned and recorded so teams can review who did what and when.", "metric": "RBAC", "metric_label": "role-based control"},
            {"label": "Scale", "title": "Templates reduce repeat work", "body": "Reusable device and site patterns keep onboarding consistent as customers add equipment.", "metric": "Templates", "metric_label": "repeatable setup"},
            {"label": "AI", "title": "AI explains operational context", "body": "The assistant should summarize trends and exceptions in plain language, not expose database or queue internals.", "metric": "Plain English", "metric_label": "operator-safe wording"},
        ],
    }),
    block("final_cta", {
        "title": "Map Novena to your site architecture",
        "subtitle": "Bring one equipment list or meter map and we will show how a pilot could be structured.",
        "primary_cta_text": "Book a platform demo",
        "primary_cta_url": "/about/#contact",
        "secondary_cta_text": "View solutions",
        "secondary_cta_url": "/solutions/",
    }),
]


SOLUTIONS_BODY = [
    block("vertical_solution_cards", HOME_BODY[3]["value"]),
    block("proof_strip", {
        "tagline": "Where Novena fits",
        "title": "A horizontal core, adapted to operational verticals.",
        "intro": "The vertical layer changes the metrics, templates, and workflows. The platform layer stays consistent.",
        "proof_points": [
            {"label": "Energy", "title": "Make utility cost visible", "body": "Track load behavior, peak periods, site comparisons, and equipment contribution.", "metric": "kW / kWh", "metric_label": "clear energy units"},
            {"label": "Cold chain", "title": "Reduce late discoveries", "body": "Escalate temperature or door events before they become inventory or compliance incidents.", "metric": "Alerts", "metric_label": "multi-channel escalation"},
            {"label": "Manufacturing", "title": "Turn machine data into work", "body": "Use run-hours, faults, and telemetry trends to trigger maintenance and operational review.", "metric": "Run-hours", "metric_label": "maintenance-ready"},
            {"label": "Facilities", "title": "Coordinate across sites", "body": "Give facility managers the same operating picture across buildings and vendors.", "metric": "Multi-site", "metric_label": "one shared view"},
        ],
    }),
    block("lead_capture", {
        "tagline": "Solution fit",
        "title": "Find the right first use case",
        "body": "Tell us what equipment or site you want to monitor. We will suggest the narrowest pilot that can prove value without over-scoping the first deployment.",
        "default_interest": "Solution fit discussion",
    }),
]


PRICING_BODY = [
    block("pricing_tiers", {
        "title": "Pricing that matches pilot, growth, and enterprise rollouts.",
        "subtitle": "Plan names and limits align with the current Novena subscription metadata. Final commercial terms can still be refined during pilot conversations.",
        "tiers": [
            {"name": "Starter", "badge": "Pilot", "price": "S$99", "period": "/mo", "features": ["1 edge gateway", "Up to 5 monitored devices", "7-day telemetry retention", "Email threshold alerts", "Best for a first equipment group"], "cta_text": "Request pilot", "cta_url": "/about/#contact", "is_popular": False},
            {"name": "Business", "badge": "Recommended", "price": "S$299", "period": "/mo", "features": ["3 edge gateways", "Up to 20 monitored devices", "30-day telemetry retention", "AI anomaly and trend support", "Grant-ready deployment documentation"], "cta_text": "Book demo", "cta_url": "/about/#contact", "is_popular": True},
            {"name": "Enterprise", "badge": "Scale", "price": "Custom", "period": "", "features": ["Custom gateway and site limits", "Up to 100 monitored devices by default", "90-day telemetry retention", "Multi-site operating model", "SLA and implementation support"], "cta_text": "Contact sales", "cta_url": "/about/#contact", "is_popular": False},
        ],
    }),
    block("pricing_comparison", {
        "title": "Compare plans",
        "features": [
            {"name": "Edge gateways included", "starter": "1", "professional": "3", "business": "Custom"},
            {"name": "Monitored devices", "starter": "5", "professional": "20", "business": "100+"},
            {"name": "Telemetry retention", "starter": "7 days", "professional": "30 days", "business": "90 days+"},
            {"name": "Email threshold alerts", "starter": "check", "professional": "check", "business": "check"},
            {"name": "AI anomaly and trend support", "starter": "-", "professional": "check", "business": "check"},
            {"name": "Multi-site management", "starter": "-", "professional": "check", "business": "check"},
            {"name": "SLA support", "starter": "-", "professional": "-", "business": "check"},
        ],
    }),
    block("faq_accordion", {
        "title": "Pricing FAQ",
        "faqs": [
            {"question": "Can we start with one gateway?", "answer": "Yes. The recommended path is a narrow pilot with one gateway and a small set of high-value assets before expanding to more sites or verticals."},
            {"question": "Do the prices include hardware?", "answer": "The public pricing communicates platform tiers. Hardware, installation, SIM/connectivity, and special integrations can be quoted separately depending on the site."},
            {"question": "Do we need real production data for a demo?", "answer": "No. A demo can use representative telemetry. A pilot uses your equipment data once the gateway is connected."},
            {"question": "Can Novena support grant-aligned deployments?", "answer": "The Business tier includes deployment documentation intended to support SME digitization and energy-efficiency conversations. Grant eligibility still depends on the relevant program rules."},
        ],
    }),
    block("lead_capture", {
        "tagline": "Pilot pricing",
        "title": "Discuss the right first plan",
        "body": "Share your site type, equipment count, and target outcome. We will recommend whether Starter, Business, or a custom pilot is the cleanest fit.",
        "default_interest": "Pricing and pilot discussion",
    }),
]


ABOUT_BODY = [
    block("proof_strip", {
        "tagline": "Mission",
        "title": "Bring modern operational software to industrial SMEs.",
        "intro": "Novena exists because many SMEs are asked to digitize without the budgets, IT teams, or integration timelines that enterprise platforms assume.",
        "proof_points": [
            {"label": "Simplicity", "title": "Reduce setup friction", "body": "The product should feel closer to deploying a managed gateway than starting a custom IIoT project.", "metric": "SME-first", "metric_label": "operator-friendly"},
            {"label": "Clarity", "title": "Explain status plainly", "body": "Customer-facing screens should use concrete language for freshness, connectivity, and action state.", "metric": "Readable", "metric_label": "no internal jargon"},
            {"label": "Trust", "title": "Be honest about proof", "body": "Public pages should avoid fake logos and inflated claims. The right tone is credible, specific, and pilot-ready.", "metric": "Credible", "metric_label": "no fake social proof"},
            {"label": "Region", "title": "Build for ASEAN operations", "body": "Singapore and ASEAN SMEs need practical digitization paths across energy, cold chain, facilities, and manufacturing.", "metric": "ASEAN", "metric_label": "local operating context"},
        ],
    }),
    block("product_visual", {
        "tagline": "Operating philosophy",
        "title": "Clear software for people who run physical operations.",
        "subtitle": "Novena combines gateway connectivity, live status, alerts, AI investigation, and operational workflows into a product surface that managers and technicians can share.",
        "visual_type": "gateway",
        "bg_color": "light_gray",
    }),
    block("lead_capture", {
        "tagline": "Contact",
        "title": "Book a practical Novena demo",
        "body": "Tell us what site, equipment, or operational problem you want to start with. We will shape the conversation around a realistic first deployment.",
        "default_interest": "General platform demo",
    }),
]


PAGE_DATA = {
    "product": {
        "title": "Platform",
        "seo_title": "Industrial IoT Platform",
        "search_description": "Explore Novena Platform: edge gateway onboarding, live monitoring, alerts, AI insights, automation, maintenance workflows, and controlled remote actions.",
        "hero_tagline": "Platform",
        "hero_title": "One industrial IoT platform from gateway to action.",
        "hero_subtitle": "Novena connects field equipment to live dashboards, AI-assisted investigation, alerts, workflows, and controlled actions without requiring every SME to build a custom IoT stack.",
        "body": PRODUCT_BODY,
    },
    "solutions": {
        "title": "Solutions",
        "seo_title": "Industrial IoT Solutions",
        "search_description": "Novena adapts its industrial IoT platform to energy monitoring, cold chain compliance, manufacturing visibility, and facilities operations.",
        "hero_tagline": "Solutions",
        "hero_title": "Vertical solutions built on one horizontal core.",
        "hero_subtitle": "Start with the business problem that matters most, then expand with the same gateway, telemetry, alerting, AI, and workflow foundation.",
        "body": SOLUTIONS_BODY,
    },
    "pricing": {
        "title": "Pricing",
        "seo_title": "Pricing",
        "search_description": "Compare Novena Starter, Business, and Enterprise plans for industrial IoT pilots, SME deployments, and multi-site operations.",
        "hero_tagline": "Pricing",
        "hero_title": "Start small. Expand when the operating value is clear.",
        "hero_subtitle": "Novena pricing is designed around gateways, monitored devices, retention, AI support, and the operational workflows needed to scale.",
        "body": PRICING_BODY,
    },
    "about": {
        "title": "About",
        "seo_title": "About Novena Platform",
        "search_description": "Learn why Novena is building AI-powered industrial IoT software for SME operations across Singapore and ASEAN.",
        "hero_tagline": "Company",
        "hero_title": "Industrial intelligence for teams that need practical deployment, not another integration project.",
        "hero_subtitle": "Novena is built for SME operators who want live visibility, useful alerts, and clear workflows across physical equipment and sites.",
        "body": ABOUT_BODY,
    },
}


def refresh_pages(apps, schema_editor):
    NovenaHomePage = apps.get_model("content", "NovenaHomePage")
    MarketingStandardPage = apps.get_model("content", "MarketingStandardPage")

    home = NovenaHomePage.objects.filter(page_ptr_id=2).first() or NovenaHomePage.objects.first()
    if home:
        home.title = "Novena Platform"
        home.seo_title = "Novena Platform"
        home.search_description = "AI-powered industrial IoT for SME operations across energy, cold chain, manufacturing, and facilities."
        home.hero_tagline = "Industrial IoT for SME operations"
        home.hero_title = "Connect equipment. See operations clearly. Act faster."
        home.hero_subtitle = (
            "Novena Platform connects meters, PLCs, sensors, and industrial assets to live dashboards, "
            "alerts, AI insights, and operational workflows built for lean teams."
        )
        home.hero_cta_text = "Book a demo"
        home.hero_cta_url = "/about/#contact"
        home.hero_secondary_cta_text = "Explore platform"
        home.hero_secondary_cta_url = "/product/"
        home.show_terminal_simulator = False
        home.body = HOME_BODY
        home.save()

    for slug, data in PAGE_DATA.items():
        page = MarketingStandardPage.objects.filter(slug=slug).first()
        if not page:
            continue
        for field in ["title", "seo_title", "search_description", "hero_tagline", "hero_title", "hero_subtitle", "body"]:
            setattr(page, field, data[field])
        page.save()


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("content", "0010_alter_marketingstandardpage_body_and_more"),
    ]

    operations = [
        migrations.RunPython(refresh_pages, noop_reverse),
    ]
