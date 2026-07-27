"""Customer-safe wording for device and remote-control presentation layers.

The machine-facing values deliberately remain unchanged.  These helpers translate
stored codes and legacy evidence only when content is shown to an operator.
"""

READINESS_STATE_LABELS = {
    "monitoring_only": "Monitoring only",
    "evidence_collecting": "More operating data needed",
    "ready_for_commissioning": "Ready for safety checks",
    "commissioning": "Safety checks in progress",
    "ready_for_activation": "Ready for customer approval",
    "active": "Remote control ready",
    "suspended": "Remote control paused",
    "recommissioning_required": "New safety checks required",
}

BLOCKER_LABELS = {
    "At least seven days of representative monitoring evidence is required.": (
        "Keep monitoring this site until at least 7 representative operating days have been recorded."
    ),
    "Telemetry coverage must be at least 95%.": (
        "Data quality is too low for safety checks. Restore device reporting and reach at least 95% usable data."
    ),
    "Gateway does not support governed-command protocol v1.": (
        "This gateway software does not support safe remote equipment control. Ask your installer to update it."
    ),
    "The installer-controlled local write-back switch is disabled.": (
        "Remote equipment control is disabled at the site. Ask an authorised technician to enable it locally."
    ),
    "Gateway has not loaded a valid retained policy.": (
        "Gateway has not confirmed the latest safety settings. Keep control blocked and reconnect or recommission it."
    ),
    "Gateway has not acknowledged the current control epoch.": (
        "Gateway has not confirmed the latest safety settings. Keep control blocked until it reconnects."
    ),
    "Gateway trusted clock is not ready.": (
        "Gateway time is not verified. Check its network connection and time settings before enabling control."
    ),
    "Gateway command journal is not ready.": (
        "Safe command history is unavailable on the gateway. Ask a technician to check gateway storage."
    ),
    "No exact template-mapped device identity is available.": (
        "No verified equipment profile is linked. Select the correct equipment model before safety checks."
    ),
}

OPERATION_LABELS = {
    "read_device": "Check equipment reading",
    "write_device": "Change equipment setting",
    "restart_gateway": "Restart gateway",
    "update_firmware": "Update gateway software",
    "ping": "Check gateway connection",
    "get_status": "Check gateway status",
}

STATUS_LABELS = {
    "requested": "Request received",
    "policy_denied": "Blocked by safety settings",
    "awaiting_approval": "Waiting for approval",
    "approved": "Approved",
    "queued_for_dispatch": "Waiting to send",
    "dispatching": "Sending to gateway",
    "publish_accepted": "Sent toward gateway",
    "broker_acknowledged": "Delivery service confirmed",
    "gateway_received": "Gateway received request",
    "executing": "Equipment action in progress",
    "field_protocol_accepted": "Equipment received request",
    "verification_pending": "Checking the result",
    "verified": "Change confirmed",
    "action_initiated": "Action started",
    "action_completed": "Action completed",
    "rejected": "Gateway rejected request",
    "failed": "Action failed",
    "expired": "Request expired",
    "timed_out": "No confirmation received",
    "cancelled": "Request cancelled",
    "outcome_unknown": "Result not confirmed — check locally",
    "reconciled_verified": "Confirmed after reconnecting",
    "reconciled_not_applied": "Confirmed not applied",
    "reconciled_unresolved": "Still not confirmed — check locally",
}

EVENT_LABELS = {
    "command_requested": "Control request recorded",
    "policy_denied": "Request blocked by safety settings",
    "approval_requested": "Approval requested",
    "command_approved": "Request approved",
    "command_queued": "Request queued for delivery",
    "dispatch_started": "Delivery started",
    "dispatch_cancelled": "Delivery cancelled safely",
    "gateway_update": "Gateway status updated",
    "command_completed": "Result recorded",
}

ERROR_LABELS = {
    "permission_denied": "You do not have permission to perform this action. Ask a site administrator for access.",
    "protocol_not_advertised": (
        "This gateway is not ready for safe remote equipment control. Ask a technician to update and recommission it."
    ),
    "capability_not_advertised": (
        "This gateway has not confirmed all required safety features. "
        "Keep remote control blocked and ask a technician to check it."
    ),
    "writeback_not_advertised": (
        "Remote equipment control is disabled at the site. Ask an authorised technician to enable it locally."
    ),
    "remote_control_revoked": "Remote control was disabled before the request could be sent.",
    "control_epoch_changed": (
        "Safety settings changed before the request could be sent. Review the latest settings and try again."
    ),
    "gateway_readiness_stale": (
        "Gateway has not confirmed the latest safety settings. Wait for it to reconnect before trying again."
    ),
    "governance_changed": "Safety settings changed before the request could be sent. Review the request and try again.",
    "commissioning_expired": "The approved safety-check period has expired. Complete the safety checks again.",
    "commissioning_missing": "This equipment setting has not completed its safety checks. Keep remote control blocked.",
    "policy_missing": "No active safety settings allow this equipment change.",
    "policy_not_acknowledged": (
        "Gateway has not confirmed the latest safety settings. Keep remote control blocked until it reconnects."
    ),
    "scope_mismatch": "This equipment setting was not included in the approved safety checks.",
    "command_expired": "The request expired before it could be sent. Check the equipment state before trying again.",
    "gateway_identity_changed": (
        "The gateway details changed. Refresh the page and confirm the correct site before trying again."
    ),
    "device_identity_changed": (
        "The equipment details changed. Refresh the page and confirm the correct equipment before trying again."
    ),
    "canonical_target_invalid": (
        "The equipment control request is incomplete. Refresh the page and select the setting again."
    ),
    "unsupported_operation": "This action is no longer available. Refresh the page or contact support.",
    "approval_expired": "The approval request expired. Review the equipment state and submit a new request.",
    "mfa_required": "Confirm your identity before approving this equipment change.",
    "recent_auth_required": "Sign in again before approving this equipment change.",
    "approval_invalidated": "The request changed after approval was requested. Review it and request approval again.",
}

UNKNOWN_SAFETY_MESSAGE = "Confirmation is unavailable. Check the equipment locally before retrying."


def readiness_state_label(value: str) -> str:
    return READINESS_STATE_LABELS.get(value, UNKNOWN_SAFETY_MESSAGE)


def readiness_blocker_label(value: str) -> str:
    return BLOCKER_LABELS.get(value, UNKNOWN_SAFETY_MESSAGE)


def operation_label(value: str) -> str:
    return OPERATION_LABELS.get(value, "Equipment control request")


def status_label(value: str) -> str:
    return STATUS_LABELS.get(value, UNKNOWN_SAFETY_MESSAGE)


def event_label(value: str) -> str:
    return EVENT_LABELS.get(value, "Safety record updated")


def customer_safe_control_error(code: str) -> str:
    return ERROR_LABELS.get(code, UNKNOWN_SAFETY_MESSAGE)


def customer_safe_device_error(message: str = "", *, code: str = "") -> str:
    """Translate ordinary device errors while keeping raw evidence in stored records/logs."""
    if code in ERROR_LABELS:
        return ERROR_LABELS[code]
    normalized = str(message or "").lower()
    if "offline" in normalized or "not online" in normalized:
        return "The Gateway is offline. Check its power and internet connection, then retry."
    if "timeout" in normalized or "timed out" in normalized:
        return "No confirmation arrived in time. Check the equipment locally before retrying."
    if "not assigned" in normalized:
        return "This equipment is not linked to a Gateway. Complete its setup before retrying."
    if "mapped" in normalized or "register" in normalized or "functioncode" in normalized:
        return "This equipment setting is not available in its verified profile. Ask a technician to review the setup."
    return UNKNOWN_SAFETY_MESSAGE
