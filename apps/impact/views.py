import csv
import json
from datetime import date

from django.contrib import messages
from django.core.files.storage import storages
from django.core.serializers.json import DjangoJSONEncoder
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.devices.models import Site
from apps.maintenance.models import MaintenanceTicket
from apps.teams.decorators import require_permission
from apps.teams.roles import has_permission

from .forms import ImpactDataSourceForm, ImpactOpportunityForm, ImpactSettingsForm
from .models import ImpactDataSource, ImpactOpportunity, ImpactReport
from .reporting import generate_report, render_report_html
from .services import (
    build_impact_readiness,
    build_site_impact_summary,
    build_team_impact_summary,
    confirm_data_source,
    ensure_site_profile,
    suggest_data_sources,
)
from .tasks import backfill_site_impact, refresh_site_impact


def _site_for_user(request, site_id, permission="view_business_impact"):
    site = get_object_or_404(Site, pk=site_id, team=request.team)
    if not has_permission(request.user, request.team, permission, site=site):
        raise Http404
    return site


def _csv_safe(value):
    text = "" if value is None else str(value)
    if text.startswith(("=", "+", "-", "@", "\t", "\r")):
        return f"'{text}"
    return text


def _can_access_report(user, team, report, permission):
    if report.site_id:
        return has_permission(user, team, permission, site=report.site)
    return all(has_permission(user, team, permission, site=site) for site in Site.objects.filter(team=team).only("id"))


@require_permission("view_business_impact")
def impact_overview(request, team_slug):
    profiles = []
    visible_site_ids = []
    for site in Site.objects.filter(team=request.team).order_by("name"):
        if not has_permission(request.user, request.team, "view_business_impact", site=site):
            continue
        profile = ensure_site_profile(site)
        visible_site_ids.append(site.id)
        profiles.append({"profile": profile, "summary": build_site_impact_summary(profile)})
    return render(
        request,
        "impact/overview.html",
        {
            "active_tab": "impact",
            "profiles": profiles,
            "team_summary": build_team_impact_summary(request.team, site_ids=visible_site_ids),
        },
    )


@require_permission("view_business_impact")
def impact_summary_json(request, team_slug):
    visible_site_ids = [
        site.id
        for site in Site.objects.filter(team=request.team).only("id")
        if has_permission(request.user, request.team, "view_business_impact", site=site)
    ]
    summary = build_team_impact_summary(request.team, site_ids=visible_site_ids)
    return JsonResponse(summary, encoder=DjangoJSONEncoder)


@require_permission("view_business_impact")
def site_impact_detail(request, team_slug, site_id):
    site = _site_for_user(request, site_id)
    profile = ensure_site_profile(site)
    summary = build_site_impact_summary(profile)
    return render(
        request,
        "impact/site_detail.html",
        {
            "active_tab": "impact",
            "site": site,
            "profile": profile,
            "summary": summary,
            "readiness": build_impact_readiness(profile, summary),
            "opportunities": profile.opportunities.select_related("source", "assigned_to")[:20],
            "assumption": profile.assumption_revisions.order_by("-revision").first(),
        },
    )


@require_permission("manage_business_impact")
def impact_settings(request, team_slug, site_id):
    site = _site_for_user(request, site_id, "manage_business_impact")
    profile = ensure_site_profile(site)
    form = ImpactSettingsForm(
        request.POST or None,
        site_profile=profile,
        user=request.user,
        can_manage_reports=has_permission(
            request.user,
            request.team,
            "manage_impact_reports",
            site=site,
        ),
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        refresh_site_impact.delay(profile.pk)
        messages.success(request, "Business assumptions saved. Novena is refreshing this site's impact metrics.")
        return redirect("web_team:impact:site_detail", team_slug=request.team.slug, site_id=site.pk)
    return render(
        request,
        "impact/settings.html",
        {"active_tab": "impact", "site": site, "profile": profile, "form": form},
    )


@require_permission("manage_business_impact")
def impact_sources(request, team_slug, site_id):
    site = _site_for_user(request, site_id, "manage_business_impact")
    profile = ensure_site_profile(site)
    suggest_data_sources(site)
    return render(
        request,
        "impact/sources.html",
        {
            "active_tab": "impact",
            "site": site,
            "profile": profile,
            "sources": profile.data_sources.select_related("device", "device__template"),
        },
    )


@require_POST
@require_permission("manage_business_impact")
def confirm_source(request, team_slug, source_id):
    source = get_object_or_404(
        ImpactDataSource.objects.select_related("site_profile", "site_profile__site", "device"),
        pk=source_id,
        team=request.team,
    )
    if not has_permission(
        request.user,
        request.team,
        "manage_business_impact",
        site=source.site_profile.site,
    ):
        raise Http404
    form = ImpactDataSourceForm(request.POST, instance=source)
    if form.is_valid():
        updated = form.save(commit=False)
        confirm_data_source(
            source,
            source_role=updated.source_role,
            include_in_totals=updated.include_in_totals,
            calibration_status=updated.calibration_status,
            calibration_accuracy=updated.calibration_accuracy,
            calibration_expires_at=updated.calibration_expires_at,
        )
        backfill_site_impact.delay(source.site_profile_id)
        messages.success(request, f"{source.device.name} · {source.telemetry_key} is confirmed for impact reporting.")
    else:
        messages.error(request, "The source mapping could not be confirmed. Review the selected role.")
    return redirect(
        "web_team:impact:sources",
        team_slug=request.team.slug,
        site_id=source.site_profile.site_id,
    )


@require_permission("view_business_impact")
def opportunity_detail(request, team_slug, opportunity_id):
    opportunity = get_object_or_404(
        ImpactOpportunity.objects.select_related("site_profile", "site_profile__site", "source", "assigned_to"),
        pk=opportunity_id,
        team=request.team,
    )
    site = opportunity.site_profile.site
    if not has_permission(request.user, request.team, "view_business_impact", site=site):
        raise Http404
    can_manage = has_permission(request.user, request.team, "manage_business_impact", site=site)
    form = ImpactOpportunityForm(
        request.POST or None,
        instance=opportunity,
        team=request.team,
    )
    if request.method == "POST":
        if not can_manage:
            raise Http404
        if form.is_valid():
            item = form.save(commit=False)
            if item.status == ImpactOpportunity.Status.RESOLVED and not item.resolved_at:
                item.resolved_at = timezone.now()
            item.save()
            messages.success(request, "Opportunity status updated.")
            return redirect(
                "web_team:impact:opportunity_detail",
                team_slug=request.team.slug,
                opportunity_id=item.pk,
            )
    return render(
        request,
        "impact/opportunity_detail.html",
        {
            "active_tab": "impact",
            "opportunity": opportunity,
            "site": site,
            "form": form,
            "can_manage": can_manage,
        },
    )


@require_POST
@require_permission("manage_business_impact")
def opportunity_create_ticket(request, team_slug, opportunity_id):
    opportunity = get_object_or_404(
        ImpactOpportunity.objects.select_related("site_profile", "site_profile__site", "source", "source__device"),
        pk=opportunity_id,
        team=request.team,
    )
    site = opportunity.site_profile.site
    if not has_permission(request.user, request.team, "manage_business_impact", site=site):
        raise Http404
    device = opportunity.source.device if opportunity.source_id else site.devices.first()
    if not device:
        messages.error(request, "Connect a device before creating maintenance work.")
        return redirect(
            "web_team:impact:opportunity_detail",
            team_slug=request.team.slug,
            opportunity_id=opportunity.pk,
        )
    ticket = MaintenanceTicket.objects.create(
        team=request.team,
        device=device,
        title=opportunity.title,
        description=opportunity.description,
        reported_by=request.user,
        priority=MaintenanceTicket.PriorityChoices.MEDIUM,
        send_email_notification=False,
        send_whatsapp_notification=False,
    )
    opportunity.tickets.add(ticket)
    opportunity.status = ImpactOpportunity.Status.ACTIONED
    opportunity.save(update_fields=["status", "updated_at"])
    messages.success(request, f"TKT-{ticket.pk} was created and linked to this opportunity.")
    return redirect("web_team:maintenance:ticket_detail", team_slug=request.team.slug, pk=ticket.pk)


@require_permission("view_business_impact")
def report_list(request, team_slug):
    reports = [
        report
        for report in ImpactReport.objects.filter(team=request.team).select_related("site")
        if _can_access_report(
            request.user,
            request.team,
            report,
            "view_business_impact",
        )
    ]
    return render(
        request,
        "impact/report_list.html",
        {"active_tab": "impact", "reports": reports},
    )


@require_POST
@require_permission("manage_impact_reports")
def report_generate(request, team_slug):
    today = timezone.localdate()
    year = int(request.POST.get("year", today.year))
    month = int(request.POST.get("month", today.month))
    if not 1 <= month <= 12 or not 2020 <= year <= today.year:
        messages.error(request, "Choose a valid report month.")
        return redirect("web_team:impact:report_list", team_slug=request.team.slug)
    period_start = date(year, month, 1)
    period_end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    site_id = request.POST.get("site_id")
    site = _site_for_user(request, int(site_id), "manage_impact_reports") if site_id else None
    try:
        report = generate_report(request.team, period_start, period_end, site=site)
    except Exception:
        messages.error(request, "The report could not be generated. The failure was recorded for support.")
        return redirect("web_team:impact:report_list", team_slug=request.team.slug)
    messages.success(request, "Business impact report generated.")
    return redirect("web_team:impact:report_detail", team_slug=request.team.slug, report_id=report.pk)


@require_permission("view_business_impact")
def report_detail(request, team_slug, report_id):
    report = get_object_or_404(ImpactReport.objects.select_related("site"), pk=report_id, team=request.team)
    if not _can_access_report(
        request.user,
        request.team,
        report,
        "view_business_impact",
    ):
        raise Http404
    return render(
        request,
        "impact/report_detail.html",
        {"active_tab": "impact", "impact_report": report, "report_html": render_report_html(report)},
    )


@require_permission("download_impact_reports")
def report_download(request, team_slug, report_id):
    report = get_object_or_404(
        ImpactReport.objects.select_related("site"),
        pk=report_id,
        team=request.team,
        status=ImpactReport.Status.READY,
    )
    if not _can_access_report(
        request.user,
        request.team,
        report,
        "download_impact_reports",
    ):
        raise Http404
    storage = storages["impact_reports"]
    if not report.private_file_name or not storage.exists(report.private_file_name):
        raise Http404
    response = FileResponse(storage.open(report.private_file_name, "rb"), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="novena-impact-{report.period_start:%Y-%m}.pdf"'
    response["Cache-Control"] = "private, no-store"
    return response


@require_permission("download_impact_reports")
def site_impact_csv(request, team_slug, site_id):
    site = _site_for_user(request, site_id, "download_impact_reports")
    profile = ensure_site_profile(site)
    snapshots = (
        profile.snapshots.filter(source__isnull=True)
        .select_related("assumption_revision")
        .order_by("-period_start", "metric_key", "-revision")
    )
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="novena-impact-site-{site.pk}.csv"'
    writer = csv.writer(response)
    writer.writerow(
        [
            "Site",
            "Period start",
            "Period end",
            "Metric",
            "Value",
            "Unit",
            "Financial estimate",
            "Currency",
            "Evidence",
            "Coverage %",
            "Confidence",
            "Methodology",
            "Assumption revision",
            "Warnings",
            "Calculation inputs",
        ]
    )
    seen = set()
    for snapshot in snapshots:
        identity = (snapshot.period_type, snapshot.period_start, snapshot.period_end, snapshot.metric_key)
        if identity in seen:
            continue
        seen.add(identity)
        writer.writerow(
            [
                _csv_safe(site.name),
                snapshot.period_start.isoformat(),
                snapshot.period_end.isoformat(),
                _csv_safe(snapshot.metric_key),
                snapshot.value,
                _csv_safe(snapshot.unit),
                snapshot.monetary_value,
                snapshot.currency,
                snapshot.evidence_class,
                snapshot.coverage_pct,
                snapshot.confidence,
                snapshot.methodology_version,
                snapshot.assumption_revision.revision if snapshot.assumption_revision_id else "",
                _csv_safe(" | ".join(snapshot.warnings)),
                _csv_safe(json.dumps(snapshot.breakdown, cls=DjangoJSONEncoder)),
            ]
        )
    return response
