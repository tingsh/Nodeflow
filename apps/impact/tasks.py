import logging
from datetime import UTC, timedelta
from zoneinfo import ZoneInfo

from celery import shared_task
from django.db.models import Min
from django.utils import timezone

from apps.teams.models import Flag
from apps.telemetry.models import TelemetryData

from .calculations import calculate_site_period, month_period, site_period_for_date
from .models import ImpactMetricSnapshot, ImpactReport, SiteImpactProfile
from .reporting import delete_private_report_file, generate_report, send_report_email
from .services import aggregate_daily_snapshots, refresh_site_baselines

logger = logging.getLogger("novena_hub")
IMPACT_FLAG_NAME = "business_impact_roi"


def _enabled_team_ids():
    flag = Flag.objects.filter(name=IMPACT_FLAG_NAME).first()
    if not flag:
        return set()
    if flag.everyone:
        return None
    return set(flag.teams.values_list("id", flat=True))


def _enabled_profiles():
    profiles = SiteImpactProfile.objects.filter(enabled=True, team__status="active")
    team_ids = _enabled_team_ids()
    return profiles if team_ids is None else profiles.filter(team_id__in=team_ids)


@shared_task
def dispatch_impact_refreshes():
    profile_ids = list(_enabled_profiles().values_list("id", flat=True))
    for profile_id in profile_ids:
        refresh_site_impact.delay(profile_id)
    return f"Queued {len(profile_ids)} impact refreshes."


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 3})
def refresh_site_impact(self, profile_id):
    profile = SiteImpactProfile.objects.select_related("site", "team").get(pk=profile_id)
    local_now = timezone.now().astimezone(ZoneInfo(profile.site.timezone))
    hour_start = local_now.replace(minute=0, second=0, microsecond=0)
    calculate_site_period(
        profile,
        hour_start.astimezone(UTC),
        timezone.now(),
        finalized=False,
    )
    start, end = site_period_for_date(profile, local_now.date())
    calculate_site_period(profile, start, min(end, timezone.now()), finalized=False)
    month_start, month_end = month_period(profile, local_now.year, local_now.month)
    aggregate_daily_snapshots(profile, month_start, month_end, finalized=False)
    return f"Refreshed impact for {profile.site.name}."


@shared_task
def dispatch_daily_impact_finalization():
    profile_ids = [
        profile.id
        for profile in _enabled_profiles().select_related("site")
        if timezone.now().astimezone(ZoneInfo(profile.site.timezone)).hour == 1
    ]
    for profile_id in profile_ids:
        finalize_previous_site_day.delay(profile_id)
    return f"Queued {len(profile_ids)} daily impact finalizations."


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 3})
def finalize_previous_site_day(self, profile_id):
    profile = SiteImpactProfile.objects.select_related("site", "team").get(pk=profile_id)
    local_today = timezone.now().astimezone(ZoneInfo(profile.site.timezone)).date()
    start, end = site_period_for_date(profile, local_today - timedelta(days=1))
    calculate_site_period(profile, start, end, finalized=True)
    refresh_site_baselines(profile)
    local_start = start.astimezone(ZoneInfo(profile.site.timezone))
    month_start, month_end = month_period(profile, local_start.year, local_start.month)
    aggregate_daily_snapshots(profile, month_start, month_end, finalized=month_end <= timezone.now())
    return f"Finalized {profile.site.name} for {start.date()}."


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 2})
def backfill_site_impact(self, profile_id, maximum_days=90):
    profile = SiteImpactProfile.objects.select_related("site", "team").get(pk=profile_id)
    earliest = TelemetryData.objects.filter(device__site=profile.site).aggregate(first=Min("timestamp"))["first"]
    if not earliest:
        return "No telemetry is available to backfill."
    zone = ZoneInfo(profile.site.timezone)
    first_date = max(
        earliest.astimezone(zone).date(),
        timezone.now().astimezone(zone).date() - timedelta(days=max(1, min(maximum_days, 90))),
    )
    last_date = timezone.now().astimezone(zone).date() - timedelta(days=1)
    processed = 0
    current = first_date
    months = set()
    while current <= last_date:
        start, end = site_period_for_date(profile, current)
        calculate_site_period(profile, start, end, finalized=True)
        refresh_site_baselines(profile)
        months.add((current.year, current.month))
        processed += 1
        current += timedelta(days=1)
    for year, month in months:
        start, end = month_period(profile, year, month)
        aggregate_daily_snapshots(profile, start, end, finalized=end <= timezone.now())
    return f"Backfilled {processed} days for {profile.site.name}."


@shared_task
def dispatch_monthly_impact_reports():
    queued = 0
    team_ids = set()
    for profile in (
        _enabled_profiles()
        .filter(
            include_in_reports=True,
            team__businessimpactprofile__reports_enabled=True,
        )
        .select_related("site", "team")
    ):
        local_now = timezone.now().astimezone(ZoneInfo(profile.site.timezone))
        if local_now.day < 2:
            continue
        previous_month_end = local_now.replace(day=1).date()
        previous_month_start = (local_now.replace(day=1) - timedelta(days=1)).replace(day=1).date()
        if ImpactReport.objects.filter(
            team=profile.team,
            site__isnull=True,
            period_start=previous_month_start,
            period_end=previous_month_end,
            status__in=[
                ImpactReport.Status.PENDING,
                ImpactReport.Status.GENERATING,
                ImpactReport.Status.READY,
            ],
        ).exists():
            continue
        team_ids.add(profile.team_id)
    for team_id in team_ids:
        generate_monthly_team_report.delay(team_id)
        queued += 1
    return f"Queued {queued} monthly impact reports."


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 3})
def generate_monthly_team_report(self, team_id):
    from apps.teams.models import Team

    team = Team.objects.get(pk=team_id, status=Team.Status.ACTIVE)
    profile = SiteImpactProfile.objects.filter(team=team, enabled=True).select_related("site").first()
    if not profile:
        return "No enabled impact sites."
    local_now = timezone.now().astimezone(ZoneInfo(profile.site.timezone))
    period_end = local_now.replace(day=1).date()
    period_start = (local_now.replace(day=1) - timedelta(days=1)).replace(day=1).date()
    report = (
        ImpactReport.objects.filter(
            team=team,
            site__isnull=True,
            period_start=period_start,
            period_end=period_end,
            status=ImpactReport.Status.READY,
        )
        .order_by("-revision")
        .first()
    )
    if not report:
        report = generate_report(team, period_start, period_end)
    send_report_email(report)
    return f"Generated impact report {report.pk}."


@shared_task
def cleanup_impact_history():
    cutoff = timezone.now() - timedelta(days=730)
    deleted_snapshots, _ = ImpactMetricSnapshot.objects.filter(period_end__lt=cutoff).delete()
    old_reports = list(ImpactReport.objects.filter(period_end__lt=cutoff.date()))
    for report in old_reports:
        delete_private_report_file(report)
    deleted_reports, _ = ImpactReport.objects.filter(period_end__lt=cutoff.date()).delete()
    return f"Deleted {deleted_snapshots} snapshot rows and {deleted_reports} report rows."
