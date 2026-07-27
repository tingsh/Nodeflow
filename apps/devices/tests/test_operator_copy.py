from django.test import SimpleTestCase

from apps.devices.operator_copy import (
    UNKNOWN_SAFETY_MESSAGE,
    customer_safe_control_error,
    event_label,
    readiness_blocker_label,
    readiness_state_label,
    status_label,
)


class OperatorCopyTests(SimpleTestCase):
    def test_status_and_event_codes_are_translated(self):
        self.assertEqual(status_label("broker_acknowledged"), "Delivery service confirmed")
        self.assertEqual(status_label("outcome_unknown"), "Result not confirmed — check locally")
        self.assertEqual(event_label("policy_denied"), "Request blocked by safety settings")

    def test_historical_blockers_are_translated_without_changing_stored_text(self):
        self.assertEqual(
            readiness_blocker_label("Gateway has not acknowledged the current control epoch."),
            "Gateway has not confirmed the latest safety settings. Keep control blocked until it reconnects.",
        )
        self.assertIn(
            "usable data",
            readiness_blocker_label("Telemetry coverage must be at least 95%."),
        )

    def test_unknown_safety_states_fail_closed(self):
        self.assertEqual(readiness_state_label("future_state"), UNKNOWN_SAFETY_MESSAGE)
        self.assertEqual(status_label("future_status"), UNKNOWN_SAFETY_MESSAGE)
        self.assertEqual(customer_safe_control_error("future_error"), UNKNOWN_SAFETY_MESSAGE)
