from django.urls import path
from waffle.decorators import waffle_flag

from . import views

app_name = "impact"

impact_flag = waffle_flag("business_impact_roi")

urlpatterns = [
    path("", impact_flag(views.impact_overview), name="overview"),
    path("summary.json", impact_flag(views.impact_summary_json), name="summary_json"),
    path("sites/<int:site_id>/", impact_flag(views.site_impact_detail), name="site_detail"),
    path("sites/<int:site_id>/settings/", impact_flag(views.impact_settings), name="settings"),
    path("sites/<int:site_id>/sources/", impact_flag(views.impact_sources), name="sources"),
    path("sources/<int:source_id>/confirm/", impact_flag(views.confirm_source), name="confirm_source"),
    path(
        "opportunities/<int:opportunity_id>/",
        impact_flag(views.opportunity_detail),
        name="opportunity_detail",
    ),
    path(
        "opportunities/<int:opportunity_id>/create-ticket/",
        impact_flag(views.opportunity_create_ticket),
        name="opportunity_create_ticket",
    ),
    path("reports/", impact_flag(views.report_list), name="report_list"),
    path("reports/generate/", impact_flag(views.report_generate), name="report_generate"),
    path("reports/<int:report_id>/", impact_flag(views.report_detail), name="report_detail"),
    path(
        "reports/<int:report_id>/download/",
        impact_flag(views.report_download),
        name="report_download",
    ),
    path(
        "sites/<int:site_id>/export.csv",
        impact_flag(views.site_impact_csv),
        name="site_csv",
    ),
]
