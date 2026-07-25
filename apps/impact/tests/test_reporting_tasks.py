from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.test import override_settings

from apps.impact.calculations import MetricResult, _persist_result
from apps.impact.models import ImpactMetricSnapshot, ImpactReport
from apps.impact.reporting import generate_report, send_report_email
from apps.impact.tasks import dispatch_impact_refreshes
from apps.teams.models import Flag, Team

from .base import ImpactTestCase


class SnapshotAndTaskIdempotenceTests(ImpactTestCase):
    def test_unfinalized_snapshot_is_updated_idempotently(self):
        start = datetime(2026, 7, 1, tzinfo=UTC)
        end = start + timedelta(days=1)
        metric = MetricResult(
            key="energy_consumption_kwh",
            value=Decimal("10"),
            unit="kWh",
            evidence=ImpactMetricSnapshot.EvidenceClass.CALCULATED,
            coverage_pct=Decimal("100"),
        )
        _persist_result(self.profile, None, start, end, metric, finalized=False)
        metric.value = Decimal("12")
        _persist_result(self.profile, None, start, end, metric, finalized=False)

        self.assertEqual(ImpactMetricSnapshot.objects.count(), 1)
        self.assertEqual(
            ImpactMetricSnapshot.objects.get().value,
            Decimal("12"),
        )

    @patch("apps.impact.tasks.refresh_site_impact.delay")
    def test_dispatch_excludes_closed_teams(self, mocked_delay):
        Flag.objects.create(name="business_impact_roi", everyone=True)
        closed_team = Team.objects.create(
            name="Closed",
            slug="closed",
            status=Team.Status.CLOSED,
        )
        type(self.site).objects.create(
            team=closed_team,
            name="Closed Site",
            solution_profile="factory_energy",
        )

        message = dispatch_impact_refreshes()

        self.assertEqual(mocked_delay.call_count, 1)
        self.assertIn("1 impact refresh", message)


class PrivateReportTests(ImpactTestCase):
    def _storage_settings(self, directory):
        return {
            "default": {
                "BACKEND": "django.core.files.storage.FileSystemStorage",
            },
            "staticfiles": {
                "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
            },
            "impact_reports": {
                "BACKEND": "django.core.files.storage.FileSystemStorage",
                "OPTIONS": {"location": directory, "base_url": None},
            },
        }

    def test_report_payload_is_frozen_and_new_generation_creates_revision(self):
        self.business.recurring_monthly_cost = Decimal("100")
        self.business.use_subscription_cost = False
        self.business.save()
        with (
            TemporaryDirectory() as directory,
            override_settings(
                STORAGES=self._storage_settings(directory),
                PRIVATE_MEDIA_ROOT=Path(directory),
            ),
            patch(
                "apps.impact.reporting.render_report_pdf",
                return_value=b"%PDF-1.4 test",
            ),
        ):
            first = generate_report(
                self.team,
                datetime(2026, 7, 1, tzinfo=UTC).date(),
                datetime(2026, 8, 1, tzinfo=UTC).date(),
            )
            frozen = first.snapshot_json
            self.business.recurring_monthly_cost = Decimal("900")
            self.business.save()
            first.refresh_from_db()
            second = generate_report(
                self.team,
                datetime(2026, 7, 1, tzinfo=UTC).date(),
                datetime(2026, 8, 1, tzinfo=UTC).date(),
            )

            self.assertEqual(first.snapshot_json, frozen)
            self.assertEqual(second.revision, 2)
            self.assertNotEqual(
                second.snapshot_json["investment_cost"],
                frozen["investment_cost"],
            )
            self.assertTrue((Path(directory) / first.private_file_name).is_file())

    def test_failed_pdf_generation_remains_auditable_without_private_file(self):
        with (
            TemporaryDirectory() as directory,
            override_settings(
                STORAGES=self._storage_settings(directory),
                PRIVATE_MEDIA_ROOT=Path(directory),
            ),
            patch(
                "apps.impact.reporting.render_report_pdf",
                side_effect=RuntimeError("renderer unavailable"),
            ),
            self.assertRaises(RuntimeError),
        ):
            generate_report(
                self.team,
                datetime(2026, 7, 1, tzinfo=UTC).date(),
                datetime(2026, 8, 1, tzinfo=UTC).date(),
            )

        report = ImpactReport.objects.get()
        self.assertEqual(report.status, ImpactReport.Status.FAILED)
        self.assertEqual(report.private_file_name, "")
        self.assertIn("renderer unavailable", report.last_error)

    @patch("apps.impact.reporting.send_tracked_email")
    def test_report_email_contains_authenticated_link_not_attachment(self, mocked_send):
        self.business.email_reports = True
        self.business.report_recipients = ["finance@example.com"]
        self.business.save()
        report = ImpactReport.objects.create(
            team=self.team,
            period_start=datetime(2026, 7, 1, tzinfo=UTC).date(),
            period_end=datetime(2026, 8, 1, tzinfo=UTC).date(),
            status=ImpactReport.Status.READY,
        )
        mocked_send.return_value = []

        send_report_email(report)

        kwargs = mocked_send.call_args.kwargs
        self.assertIn("/impact/reports/", kwargs["text_body"])
        self.assertNotIn("attachments", kwargs)
