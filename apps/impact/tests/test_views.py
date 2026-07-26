import json
from datetime import UTC, datetime
from decimal import Decimal

from django.test import Client
from django.urls import reverse

from apps.devices.models import SiteMembershipAccess
from apps.impact.models import ImpactMetricSnapshot, ImpactReport
from apps.teams.models import Flag, Membership, Team
from apps.teams.roles import ROLE_MANAGER, ROLE_OWNER, ROLE_VIEWER
from apps.users.models import CustomUser

from .base import ImpactTestCase


class ImpactViewSecurityTests(ImpactTestCase):
    def setUp(self):
        super().setUp()
        Flag.objects.create(name="business_impact_roi", everyone=True)
        self.owner = CustomUser.objects.create_user(
            username="impact-owner",
            email="owner@example.com",
            password="password",
        )
        self.viewer = CustomUser.objects.create_user(
            username="impact-viewer",
            email="viewer@example.com",
            password="password",
        )
        Membership.objects.create(
            team=self.team,
            user=self.owner,
            role=ROLE_OWNER,
        )
        self.viewer_membership = Membership.objects.create(
            team=self.team,
            user=self.viewer,
            role=ROLE_VIEWER,
        )
        self.client = Client()

    def test_feature_flag_returns_404_when_disabled(self):
        Flag.objects.filter(name="business_impact_roi").update(everyone=False)
        self.client.force_login(self.owner)
        response = self.client.get(reverse("web_team:impact:overview", args=[self.team.slug]))
        self.assertEqual(response.status_code, 404)

    def test_viewer_can_view_but_cannot_manage_assumptions(self):
        self.client.force_login(self.viewer)
        detail = self.client.get(
            reverse(
                "web_team:impact:site_detail",
                args=[self.team.slug, self.site.id],
            )
        )
        settings = self.client.get(
            reverse(
                "web_team:impact:settings",
                args=[self.team.slug, self.site.id],
            )
        )
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(settings.status_code, 403)

    def test_cross_tenant_report_identifier_is_not_disclosed(self):
        other_team = Team.objects.create(name="Other", slug="other")
        report = ImpactReport.objects.create(
            team=other_team,
            period_start=datetime(2026, 7, 1, tzinfo=UTC).date(),
            period_end=datetime(2026, 8, 1, tzinfo=UTC).date(),
            status=ImpactReport.Status.READY,
            private_file_name="private.pdf",
        )
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse(
                "web_team:impact:report_download",
                args=[self.team.slug, report.id],
            )
        )
        self.assertEqual(response.status_code, 404)

    def test_site_limited_member_cannot_view_team_report_for_other_sites(self):
        second_site = type(self.site).objects.create(
            team=self.team,
            name="Restricted Site",
            solution_profile="factory_energy",
        )
        SiteMembershipAccess.objects.create(
            team=self.team,
            membership=self.viewer_membership,
            site=self.site,
        )
        report = ImpactReport.objects.create(
            team=self.team,
            period_start=datetime(2026, 7, 1, tzinfo=UTC).date(),
            period_end=datetime(2026, 8, 1, tzinfo=UTC).date(),
            status=ImpactReport.Status.READY,
            snapshot_json={"sites": [{"site_id": self.site.id}, {"site_id": second_site.id}]},
        )
        self.client.force_login(self.viewer)
        response = self.client.get(
            reverse(
                "web_team:impact:report_detail",
                args=[self.team.slug, report.id],
            )
        )
        self.assertEqual(response.status_code, 404)

    def test_site_limited_member_summary_excludes_other_site_financials(self):
        second_site = type(self.site).objects.create(
            team=self.team,
            name="Restricted Site",
            solution_profile="factory_energy",
        )
        second_profile = second_site.impact_profile
        SiteMembershipAccess.objects.create(
            team=self.team,
            membership=self.viewer_membership,
            site=self.site,
        )
        period_start = datetime(2026, 7, 1, tzinfo=UTC)
        period_end = datetime(2026, 8, 1, tzinfo=UTC)
        for profile, value in ((self.profile, Decimal("10")), (second_profile, Decimal("9999"))):
            ImpactMetricSnapshot.objects.create(
                team=self.team,
                site_profile=profile,
                period_type=ImpactMetricSnapshot.PeriodType.MONTHLY,
                period_start=period_start,
                period_end=period_end,
                metric_key="estimated_realized_value",
                evidence_class=ImpactMetricSnapshot.EvidenceClass.ESTIMATED,
                monetary_value=value,
                currency="SGD",
                coverage_pct=Decimal("100"),
                confidence=ImpactMetricSnapshot.Confidence.NORMAL,
            )

        self.client.force_login(self.viewer)
        response = self.client.get(
            reverse("web_team:impact:summary_json", args=[self.team.slug]),
        )

        self.assertEqual(response.status_code, 200)
        site_ids = {site_summary["site_id"] for site_summary in response.json()["sites"]}
        self.assertEqual(site_ids, {self.site.id})
        self.assertNotContains(response, "9999")

    def test_csv_protects_formula_cells_and_exposes_evidence(self):
        self.site.name = "=SUM(1,1)"
        self.site.save()
        assumption = self.profile.assumption_revisions.first()
        ImpactMetricSnapshot.objects.create(
            team=self.team,
            site_profile=self.profile,
            period_type=ImpactMetricSnapshot.PeriodType.MONTHLY,
            period_start=datetime(2026, 7, 1, tzinfo=UTC),
            period_end=datetime(2026, 8, 1, tzinfo=UTC),
            metric_key="estimated_realized_value",
            evidence_class=ImpactMetricSnapshot.EvidenceClass.ESTIMATED,
            monetary_value=Decimal("12.34"),
            currency="SGD",
            coverage_pct=Decimal("99"),
            confidence=ImpactMetricSnapshot.Confidence.NORMAL,
            assumption_revision=assumption,
            breakdown={"tariff": "=unsafe"},
        )
        self.client.force_login(self.viewer)
        response = self.client.get(
            reverse(
                "web_team:impact:site_csv",
                args=[self.team.slug, self.site.id],
            )
        )
        body = response.content.decode()
        self.assertEqual(response.status_code, 200)
        self.assertIn("'=SUM(1,1)", body)
        self.assertIn("Assumption revision", body)
        self.assertIn("estimated", body)
        self.assertIn(json.dumps({"tariff": "=unsafe"}).replace('"', '""'), body)

    def test_manager_cannot_generate_team_report(self):
        manager = CustomUser.objects.create_user(
            username="impact-manager",
            email="manager@example.com",
            password="password",
        )
        Membership.objects.create(team=self.team, user=manager, role=ROLE_MANAGER)
        self.client.force_login(manager)
        response = self.client.post(
            reverse("web_team:impact:report_generate", args=[self.team.slug]),
            {"year": 2026, "month": 7},
        )
        self.assertEqual(response.status_code, 403)
