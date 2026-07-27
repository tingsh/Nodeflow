from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

from apps.devices.config_generator import normalized_datapoints
from apps.impact.calculations import MetricResult, month_period
from apps.impact.models import (
    ImpactBaseline,
    ImpactDataSource,
    ImpactMetricSnapshot,
)
from apps.impact.services import (
    build_impact_readiness,
    build_site_impact_summary,
    build_team_impact_summary,
    confirm_data_source,
    infer_datapoint_semantics,
    monthly_investment_cost,
    monthly_recurring_investment_cost,
    refresh_site_baselines,
)

from .base import ImpactTestCase


class SemanticAndTopologyServiceTests(ImpactTestCase):
    def test_impact_readiness_uses_operator_language(self):
        summary = build_site_impact_summary(self.profile, 2026, 7)
        readiness = build_impact_readiness(self.profile, summary)
        labels = {item["label"] for item in readiness}
        details = " ".join(item["detail"] for item in readiness)

        self.assertIn("Meter or sensor confirmed", labels)
        self.assertIn("Usable operating data", labels)
        self.assertIn("usable readings", details)
        self.assertNotIn("semantic mapping", details)

    def test_semantic_unit_conversion_requires_known_units(self):
        semantics = infer_datapoint_semantics("active_power", {"unit": "W"})
        self.assertEqual(semantics[:3], ("power", "instantaneous", "kW"))
        self.assertEqual(semantics[3], Decimal("0.001"))
        self.assertIsNone(infer_datapoint_semantics("active_power", {"unit": "horsepower"}))

    def test_normalized_datapoint_v2_exposes_impact_semantics(self):
        template = self.create_template(
            {
                "active_power": {
                    "unit": "W",
                    "plausibility": {"min": 0, "max": 100000},
                }
            }
        )
        datapoint = normalized_datapoints(template)[0]

        self.assertEqual(template.datapoint_schema_version, 2)
        self.assertEqual(datapoint["quantity_kind"], "power")
        self.assertEqual(datapoint["aggregation"], "instantaneous")
        self.assertEqual(datapoint["canonical_unit"], "kW")
        self.assertEqual(datapoint["conversion_factor"], "0.001")

    def test_coverage_confidence_gates(self):
        metric = MetricResult(
            key="value",
            value=Decimal("1"),
            unit="",
            evidence=ImpactMetricSnapshot.EvidenceClass.ESTIMATED,
            coverage_pct=Decimal("79.99"),
        )
        self.assertEqual(
            metric.confidence,
            ImpactMetricSnapshot.Confidence.WITHHELD,
        )
        metric.coverage_pct = Decimal("80")
        self.assertEqual(metric.confidence, ImpactMetricSnapshot.Confidence.LOW)
        metric.coverage_pct = Decimal("95")
        self.assertEqual(metric.confidence, ImpactMetricSnapshot.Confidence.NORMAL)

    def test_confirming_boundary_disables_previous_energy_total(self):
        template = self.create_template({"energy": {"unit": "kWh"}})
        first = self.create_source(
            self.create_device(template, name="First"),
            "energy",
        )
        second = self.create_source(
            self.create_device(template, name="Second"),
            "energy",
            role=ImpactDataSource.SourceRole.SUBMETER,
            include=False,
        )

        confirm_data_source(
            second,
            source_role=ImpactDataSource.SourceRole.SITE_BOUNDARY,
            include_in_totals=True,
        )
        first.refresh_from_db()

        self.assertFalse(first.include_in_totals)
        self.assertTrue(second.include_in_totals)


class BaselineAndRoiServiceTests(ImpactTestCase):
    def _daily_snapshot(self, day, value, *, coverage=Decimal("100")):
        start = datetime(2026, 6, day, tzinfo=UTC)
        return ImpactMetricSnapshot.objects.create(
            team=self.team,
            site_profile=self.profile,
            period_type=ImpactMetricSnapshot.PeriodType.DAILY,
            period_start=start,
            period_end=start + timedelta(days=1),
            metric_key="energy_consumption_kwh",
            evidence_class=ImpactMetricSnapshot.EvidenceClass.CALCULATED,
            value=value,
            unit="kWh",
            coverage_pct=coverage,
            confidence=ImpactMetricSnapshot.Confidence.NORMAL,
            finalized=True,
        )

    def test_baseline_requires_four_week_window_and_fourteen_good_days(self):
        for day in range(1, 15):
            self._daily_snapshot(day, Decimal("100"))
        baselines = refresh_site_baselines(self.profile)

        self.assertEqual(len(baselines), 1)
        baseline = ImpactBaseline.objects.get(metric_key="energy_consumption_kwh")
        self.assertEqual(baseline.values["comparable_days"], 14)
        self.assertEqual(baseline.values["daily_average"], "100.000000")
        self.assertEqual(set(baseline.values["weekday_daily_average"]), {str(day) for day in range(7)})

    @patch("apps.impact.services.subscription_monthly_cost", return_value=Decimal("100"))
    def test_payback_run_rate_includes_subscription_and_manual_recurring_cost(self, _subscription_cost):
        self.business.one_time_investment = Decimal("1000")
        self.business.amortization_months = 10
        self.business.recurring_monthly_cost = Decimal("50")
        self.business.use_subscription_cost = True
        self.business.save()
        start, end = month_period(self.profile, 2026, 7)
        ImpactMetricSnapshot.objects.create(
            team=self.team,
            site_profile=self.profile,
            period_type=ImpactMetricSnapshot.PeriodType.MONTHLY,
            period_start=start,
            period_end=end,
            metric_key="estimated_realized_value",
            evidence_class=ImpactMetricSnapshot.EvidenceClass.ESTIMATED,
            monetary_value=Decimal("300"),
            currency="SGD",
            coverage_pct=Decimal("100"),
            confidence=ImpactMetricSnapshot.Confidence.NORMAL,
        )

        summary = build_site_impact_summary(self.profile, 2026, 7)

        self.assertEqual(monthly_recurring_investment_cost(self.business), Decimal("150.00"))
        self.assertEqual(summary.investment_cost, Decimal("250.00"))
        self.assertEqual(summary.payback_months, Decimal("6.7"))

    def test_investment_uses_decimal_amortization_and_site_allocation(self):
        self.business.one_time_investment = Decimal("2400")
        self.business.amortization_months = 24
        self.business.recurring_monthly_cost = Decimal("100")
        self.business.use_subscription_cost = False
        self.business.save()
        self.assertEqual(monthly_investment_cost(self.business), Decimal("200.00"))

        second_site = type(self.site).objects.create(
            team=self.team,
            name="Second Site",
            solution_profile="factory_energy",
        )
        second_profile = second_site.impact_profile
        start, end = month_period(self.profile, 2026, 7)
        for profile in (self.profile, second_profile):
            ImpactMetricSnapshot.objects.create(
                team=self.team,
                site_profile=profile,
                period_type=ImpactMetricSnapshot.PeriodType.MONTHLY,
                period_start=start,
                period_end=end,
                metric_key="estimated_realized_value",
                evidence_class=ImpactMetricSnapshot.EvidenceClass.ESTIMATED,
                monetary_value=Decimal("150"),
                currency="SGD",
                coverage_pct=Decimal("100"),
                confidence=ImpactMetricSnapshot.Confidence.NORMAL,
            )

        summary = build_site_impact_summary(self.profile, 2026, 7)
        team_summary = build_team_impact_summary(self.team, 2026, 7)
        scoped_summary = build_team_impact_summary(self.team, 2026, 7, site_ids=[self.site.id])

        self.assertEqual(summary.investment_cost, Decimal("100.00"))
        self.assertEqual(team_summary["investment_cost"], Decimal("200.00"))
        self.assertEqual(team_summary["estimated_realized_value"], Decimal("300"))
        self.assertEqual(team_summary["net_benefit"], Decimal("100.00"))
        self.assertEqual(team_summary["roi_pct"], Decimal("50.0"))
        self.assertEqual(scoped_summary["investment_cost"], Decimal("100.00"))
        self.assertEqual(scoped_summary["estimated_realized_value"], Decimal("150"))

    def test_mixed_currency_withholds_invalid_site_financial_total(self):
        self.business.currency = "SGD"
        self.business.recurring_monthly_cost = Decimal("100")
        self.business.use_subscription_cost = False
        self.business.save()
        start, end = month_period(self.profile, 2026, 7)
        ImpactMetricSnapshot.objects.create(
            team=self.team,
            site_profile=self.profile,
            period_type=ImpactMetricSnapshot.PeriodType.MONTHLY,
            period_start=start,
            period_end=end,
            metric_key="estimated_realized_value",
            evidence_class=ImpactMetricSnapshot.EvidenceClass.ESTIMATED,
            monetary_value=Decimal("500"),
            currency="USD",
            coverage_pct=Decimal("100"),
            confidence=ImpactMetricSnapshot.Confidence.NORMAL,
        )

        summary = build_site_impact_summary(self.profile, 2026, 7)

        self.assertIsNone(summary.estimated_realized_value)
        self.assertIsNone(summary.roi_pct)
        self.assertTrue(any("currencies differ" in warning for warning in summary.warnings))
