import json
import logging
from datetime import date

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import storages
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.db.models import Max
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from apps.events.models import EmailDelivery
from apps.events.services import TrackedEmailDeliveryError, send_tracked_email
from apps.web.meta import absolute_url

from .models import ImpactReport
from .services import (
    build_site_impact_summary,
    build_team_impact_summary,
    ensure_business_profile,
    ensure_site_profile,
)

logger = logging.getLogger("novena_hub")


def _json_safe(value):
    return json.loads(json.dumps(value, cls=DjangoJSONEncoder))


def _report_context(report):
    period_label = report.period_start.strftime("%B %Y")
    return {
        "report": report,
        "team": report.team,
        "site": report.site,
        "period_label": period_label,
        "summary": report.snapshot_json,
        "generated_at": report.generated_at or timezone.now(),
        "methodology_version": report.methodology_version,
    }


def render_report_html(report):
    return render_to_string("impact/report.html", _report_context(report))


def render_report_pdf(report):
    try:
        from weasyprint import HTML
    except ImportError as exc:
        raise RuntimeError("WeasyPrint is required to render business impact PDFs.") from exc
    html = render_report_html(report)
    return HTML(string=html, base_url=str(settings.BASE_DIR)).write_pdf()


def generate_report(team, period_start, period_end, *, site=None, revision=None):
    period_start = period_start if isinstance(period_start, date) else period_start.date()
    period_end = period_end if isinstance(period_end, date) else period_end.date()
    if site is not None and site.team_id != team.id:
        raise ValueError("The report site must belong to the requested team.")
    with transaction.atomic():
        team = type(team).objects.select_for_update().get(pk=team.pk)
        report_rows = ImpactReport.objects.select_for_update().filter(
            team=team,
            site=site,
            period_start=period_start,
            period_end=period_end,
        )
        revision = revision or ((report_rows.aggregate(max_revision=Max("revision"))["max_revision"] or 0) + 1)
        report = ImpactReport.objects.create(
            team=team,
            site=site,
            period_start=period_start,
            period_end=period_end,
            revision=revision,
            status=ImpactReport.Status.GENERATING,
        )
    try:
        if site:
            snapshot = build_site_impact_summary(
                ensure_site_profile(site),
                period_start.year,
                period_start.month,
            ).to_dict()
        else:
            snapshot = build_team_impact_summary(team, period_start.year, period_start.month)
        report.snapshot_json = _json_safe(snapshot)
        report.generated_at = timezone.now()
        report.save(update_fields=["snapshot_json", "generated_at", "updated_at"])
        pdf_bytes = render_report_pdf(report)
        file_name = f"impact-reports/team-{team.pk}/report-{report.pk}-r{report.revision}.pdf"
        report.private_file_name = storages["impact_reports"].save(file_name, ContentFile(pdf_bytes))
        report.status = ImpactReport.Status.READY
        report.last_error = ""
        report.save(update_fields=["private_file_name", "status", "last_error", "generated_at", "updated_at"])
    except Exception as exc:
        delete_private_report_file(report)
        report.private_file_name = ""
        report.status = ImpactReport.Status.FAILED
        report.last_error = str(exc)
        report.save(update_fields=["private_file_name", "status", "last_error", "updated_at"])
        logger.exception("Business impact report %s failed", report.pk)
        raise
    return report


def delete_private_report_file(report):
    if not report.private_file_name:
        return
    storage = storages["impact_reports"]
    if storage.exists(report.private_file_name):
        storage.delete(report.private_file_name)


def send_report_email(report):
    profile = ensure_business_profile(report.team)
    if not profile.email_reports or report.status != ImpactReport.Status.READY:
        return []
    recipients = sorted({email.strip().lower() for email in profile.report_recipients if email.strip()})
    if not recipients:
        return []
    report_url = absolute_url(
        reverse(
            "web_team:impact:report_detail",
            args=[report.team.slug, report.pk],
        )
    )
    subject = f"[Novena] {report.period_start:%B %Y} Business Impact Review"
    text_body = (
        f"Your Novena business impact review for {report.period_start:%B %Y} is ready.\n\n"
        f"Open the authenticated report: {report_url}\n\n"
        "The report separates measured results, calculated metrics, and estimates. "
        "Financial estimates show the assumptions and data coverage used."
    )
    try:
        deliveries = send_tracked_email(
            team=report.team,
            notification_type=EmailDelivery.NotificationType.IMPACT_REPORT,
            subject=subject,
            text_body=text_body,
            recipients=recipients,
            metadata={
                "idempotency_key": f"impact-report:{report.pk}:r{report.revision}",
                "impact_report_id": report.pk,
            },
        )
    except TrackedEmailDeliveryError:
        logger.exception("One or more impact report deliveries failed for report %s", report.pk)
        raise
    report.emailed_at = timezone.now()
    report.save(update_fields=["emailed_at", "updated_at"])
    return deliveries
