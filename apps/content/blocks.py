from django.utils.html import format_html
from django.utils.safestring import mark_safe
from wagtail import blocks

class CaptionBlock(blocks.TextBlock):
    """
    A block for generating <figcaptions> that can also use html characters (so you can add, e.g. links).
    """

    def render_basic(self, value, context=None):
        if value:
            return format_html("<figcaption>{0}</figcaption>", mark_safe(value))
        else:
            return ""

    class Meta:
        icon = "info-circle"


class TrustedByBlock(blocks.StructBlock):
    tagline = blocks.CharBlock(required=False, default="Empowering Industry Leaders Across ASEAN")
    companies = blocks.ListBlock(blocks.CharBlock(label="Company Name"))

    class Meta:
        template = "content/blocks/trusted_by.html"
        icon = "group"
        label = "Trusted By / Partners"


class FeatureCardBlock(blocks.StructBlock):
    icon = blocks.CharBlock(required=True, default="fa-chart-line", help_text="FontAwesome class name")
    title = blocks.CharBlock(required=True)
    description = blocks.TextBlock(required=True)
    link_text = blocks.CharBlock(required=False)
    link_url = blocks.CharBlock(required=False)


class FeatureGridBlock(blocks.StructBlock):
    tagline = blocks.CharBlock(required=False, default="Core Capabilities")
    title = blocks.CharBlock(required=True, default="Engineered for Extreme Operational Resilience.")
    features = blocks.ListBlock(FeatureCardBlock())

    class Meta:
        template = "content/blocks/feature_grid.html"
        icon = "grid"
        label = "Feature Grid"


class AISpotlightBlock(blocks.StructBlock):
    tagline = blocks.CharBlock(required=False, default="Built-in Intelligence")
    title = blocks.CharBlock(required=True, default="Stop searching for logs. Start asking questions.")
    body = blocks.TextBlock(required=True)
    prompt_text = blocks.CharBlock(required=True, default="Show yesterday's efficiency trends for Factory Floor A.")
    response_tagline = blocks.CharBlock(required=False, default="Novena AI")
    response_text = blocks.TextBlock(required=True)

    class Meta:
        template = "content/blocks/ai_spotlight.html"
        icon = "code"
        label = "AI Spotlight"


class FinalCTABlock(blocks.StructBlock):
    title = blocks.CharBlock(required=True, default="Ready to secure your operations?")
    subtitle = blocks.CharBlock(required=True, default="Connect your first edge gateway in 24 hours. Activate your pilot program today.")
    primary_cta_text = blocks.CharBlock(required=True, default="Activate Pilot Program")
    primary_cta_url = blocks.CharBlock(required=True, default="/accounts/signup/")
    secondary_cta_text = blocks.CharBlock(required=False, default="See Plans & Pricing")
    secondary_cta_url = blocks.CharBlock(required=False, default="/pricing/")

    class Meta:
        template = "content/blocks/final_cta.html"
        icon = "plus"
        label = "Final Call to Action"


class FeatureSectionBlock(blocks.StructBlock):
    title = blocks.CharBlock(required=True)
    description = blocks.TextBlock(required=True)
    icon = blocks.CharBlock(required=False, default="fa-chart-line")
    badge = blocks.CharBlock(required=False)
    check_items = blocks.ListBlock(blocks.CharBlock(label="Bullet Point"), required=False)
    mockup_type = blocks.ChoiceBlock(choices=[
        ("dashboard", "Dashboard Mockup"),
        ("ai_chat", "AI Chat Mockup"),
        ("remote_control", "Remote Control Mockup"),
        ("multi_wan", "Multi-WAN Active Watchdog"),
    ], default="dashboard")
    mockup_title = blocks.CharBlock(required=False, default="Mockup")
    align_image = blocks.ChoiceBlock(choices=[
        ("left", "Image Left"),
        ("right", "Image Right"),
    ], default="right")
    bg_color = blocks.ChoiceBlock(choices=[
        ("white", "White"),
        ("light_gray", "Light Gray"),
        ("dark_indigo", "Dark Indigo"),
    ], default="white")

    class Meta:
        template = "content/blocks/feature_section.html"
        icon = "doc-full-blank"
        label = "Feature Section (Product Layout)"


class PricingTierBlock(blocks.StructBlock):
    name = blocks.CharBlock(required=True)
    badge = blocks.CharBlock(required=False)
    price = blocks.CharBlock(required=True)
    period = blocks.CharBlock(required=False, default="/mo")
    features = blocks.ListBlock(blocks.CharBlock(label="Feature Item"))
    cta_text = blocks.CharBlock(required=True, default="Get Started")
    cta_url = blocks.CharBlock(required=True, default="/accounts/signup/")
    is_popular = blocks.BooleanBlock(required=False, default=False)


class PricingTiersBlock(blocks.StructBlock):
    title = blocks.CharBlock(required=False, default="Simple, fair pricing.")
    subtitle = blocks.CharBlock(required=False, default="No hidden device fees. No complex throughput math.")
    tiers = blocks.ListBlock(PricingTierBlock())

    class Meta:
        template = "content/blocks/pricing_tiers.html"
        icon = "table"
        label = "Pricing Tiers Grid"


class ComparisonFeatureRow(blocks.StructBlock):
    name = blocks.CharBlock(required=True)
    starter = blocks.CharBlock(required=True)
    professional = blocks.CharBlock(required=True)
    business = blocks.CharBlock(required=True)


class PricingComparisonBlock(blocks.StructBlock):
    title = blocks.CharBlock(required=False, default="Compare Features")
    features = blocks.ListBlock(ComparisonFeatureRow())

    class Meta:
        template = "content/blocks/pricing_comparison.html"
        icon = "list-ul"
        label = "Pricing Comparison Table"


class FAQAccordionBlock(blocks.StructBlock):
    title = blocks.CharBlock(required=False, default="Frequently Asked Questions")
    faqs = blocks.ListBlock(blocks.StructBlock([
        ("question", blocks.CharBlock(required=True)),
        ("answer", blocks.TextBlock(required=True)),
    ]))

    class Meta:
        template = "content/blocks/faq_accordion.html"
        icon = "help"
        label = "FAQ Accordion"


class SolutionsSectionBlock(blocks.StructBlock):
    badge = blocks.CharBlock(required=True)
    title = blocks.CharBlock(required=True)
    pain_point_text = blocks.TextBlock(required=True)
    solution_text = blocks.TextBlock(required=True)
    illustration_type = blocks.ChoiceBlock(choices=[
        ("grid", "Grids/Stats"),
        ("snowflake", "Snowflake Icon"),
        ("gear", "Rotating Gear"),
    ], default="grid")
    align_image = blocks.ChoiceBlock(choices=[
        ("left", "Image Left"),
        ("right", "Image Right"),
    ], default="right")
    bg_color = blocks.ChoiceBlock(choices=[
        ("white", "White"),
        ("light_gray", "Light Gray"),
    ], default="white")

    class Meta:
        template = "content/blocks/solutions_section.html"
        icon = "tasks"
        label = "Solution Section (Verticals)"


class HeroBlock(blocks.StructBlock):
    tagline = blocks.CharBlock(required=False, default="Industrial Intelligence")
    title = blocks.CharBlock(required=True, default="Your Factory, Perfectly Synchronized.")
    subtitle = blocks.CharBlock(required=True)
    primary_cta_text = blocks.CharBlock(required=True, default="Activate Cloud Access")
    primary_cta_url = blocks.CharBlock(required=True, default="/accounts/signup/")
    secondary_cta_text = blocks.CharBlock(required=False, default="Explore Platform")
    secondary_cta_url = blocks.CharBlock(required=False, default="#features")
    bg_style = blocks.ChoiceBlock(choices=[
        ("light", "Light Background"),
        ("dark", "Dark Background"),
    ], default="light")
    show_terminal_simulator = blocks.BooleanBlock(required=False, default=True)

    class Meta:
        template = "content/blocks/hero.html"
        icon = "home"
        label = "Hero Section"
