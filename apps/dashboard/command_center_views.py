import json

from django.db import transaction
from django.http import Http404, JsonResponse
from django.views.decorators.http import require_POST
from waffle import flag_is_active

from apps.devices.models import Site
from apps.events.services import log_event
from apps.teams.decorators import require_permission
from apps.teams.roles import has_permission

from .command_center import (
    LayoutValidationError,
    available_panel_ids,
    normalize_layout,
    resolve_layout,
    validate_layout_payload,
)
from .models import CommandCenterLayout

MAX_LAYOUT_PAYLOAD_BYTES = 20_000


def _require_feature(request):
    if not flag_is_active(request, "command_center_customization"):
        raise Http404


def _json_payload(request):
    try:
        content_length = int(request.META.get("CONTENT_LENGTH") or 0)
    except (TypeError, ValueError) as exc:
        raise LayoutValidationError("The layout payload length is invalid.") from exc
    if content_length > MAX_LAYOUT_PAYLOAD_BYTES or len(request.body) > MAX_LAYOUT_PAYLOAD_BYTES:
        raise LayoutValidationError("The layout payload is too large.")
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LayoutValidationError("The layout payload must be valid JSON.") from exc
    if not isinstance(payload, dict):
        raise LayoutValidationError("The layout payload must be an object.")
    return payload


def _error(message, *, status=400, code="invalid_layout"):
    return JsonResponse({"code": code, "message": message}, status=status)


def _base_revision(payload):
    revision = payload.get("base_revision", 0)
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 0:
        raise LayoutValidationError("The base revision must be a non-negative integer.")
    return revision


def _include_impact(request):
    if not flag_is_active(request, "business_impact_roi"):
        return False
    return any(
        has_permission(request.user, request.team, "view_business_impact", site=site)
        for site in Site.objects.filter(team=request.team).only("id")
    )


def _resolution_response(team, user):
    resolution = resolve_layout(team, user)
    return JsonResponse(
        {
            "layout": resolution["layout"],
            "source": resolution["source"],
            "personal_revision": resolution["personal_revision"],
            "team_default_revision": resolution["team_default_revision"],
        }
    )


@require_permission("view_dashboard")
@require_POST
def save_personal_layout(request, team_slug):
    _require_feature(request)
    try:
        payload = _json_payload(request)
        base_revision = _base_revision(payload)
    except LayoutValidationError as exc:
        return _error(str(exc))

    include_impact = _include_impact(request)
    with transaction.atomic():
        existing = (
            CommandCenterLayout.objects.select_for_update()
            .filter(
                team=request.team,
                user=request.user,
                scope=CommandCenterLayout.Scope.PERSONAL,
            )
            .first()
        )
        current_revision = existing.revision if existing else 0
        if base_revision != current_revision:
            return _error(
                "This layout changed in another browser tab. Reload before saving again.",
                status=409,
                code="revision_conflict",
            )

        base_layout = existing.layout if existing else resolve_layout(request.team, request.user)["layout"]
        try:
            layout = validate_layout_payload(
                payload,
                available_ids=available_panel_ids(include_impact=include_impact),
                base_layout=base_layout,
            )
        except LayoutValidationError as exc:
            return _error(str(exc))

        if existing:
            existing.layout = layout
            existing.schema_version = layout["schema_version"]
            existing.revision += 1
            existing.updated_by = request.user
            existing.save(update_fields=["layout", "schema_version", "revision", "updated_by", "updated_at"])
        else:
            CommandCenterLayout.objects.create(
                team=request.team,
                user=request.user,
                scope=CommandCenterLayout.Scope.PERSONAL,
                layout=layout,
                schema_version=layout["schema_version"],
                revision=1,
                updated_by=request.user,
            )
    return _resolution_response(request.team, request.user)


@require_permission("view_dashboard")
@require_POST
def reset_personal_layout(request, team_slug):
    _require_feature(request)
    try:
        payload = _json_payload(request)
        base_revision = _base_revision(payload)
    except LayoutValidationError as exc:
        return _error(str(exc))

    with transaction.atomic():
        existing = (
            CommandCenterLayout.objects.select_for_update()
            .filter(
                team=request.team,
                user=request.user,
                scope=CommandCenterLayout.Scope.PERSONAL,
            )
            .first()
        )
        current_revision = existing.revision if existing else 0
        if base_revision != current_revision:
            return _error(
                "This layout changed in another browser tab. Reload before resetting it.",
                status=409,
                code="revision_conflict",
            )
        if existing:
            existing.delete()
    return _resolution_response(request.team, request.user)


@require_permission("manage_team")
@require_POST
def publish_team_default(request, team_slug):
    _require_feature(request)
    try:
        payload = _json_payload(request)
        base_revision = _base_revision(payload)
    except LayoutValidationError as exc:
        return _error(str(exc))

    with transaction.atomic():
        team_default = (
            CommandCenterLayout.objects.select_for_update()
            .filter(team=request.team, scope=CommandCenterLayout.Scope.TEAM_DEFAULT)
            .first()
        )
        current_revision = team_default.revision if team_default else 0
        if base_revision != current_revision:
            return _error(
                "The team default changed in another browser tab. Reload before publishing again.",
                status=409,
                code="revision_conflict",
            )

        personal = CommandCenterLayout.objects.filter(
            team=request.team,
            user=request.user,
            scope=CommandCenterLayout.Scope.PERSONAL,
        ).first()
        source_layout = personal.layout if personal else resolve_layout(request.team, request.user)["layout"]
        published_layout = normalize_layout(source_layout)
        if team_default:
            team_default.layout = published_layout
            team_default.schema_version = published_layout["schema_version"]
            team_default.revision += 1
            team_default.updated_by = request.user
            team_default.save(
                update_fields=["layout", "schema_version", "revision", "updated_by", "updated_at"]
            )
        else:
            CommandCenterLayout.objects.create(
                team=request.team,
                user=None,
                scope=CommandCenterLayout.Scope.TEAM_DEFAULT,
                layout=published_layout,
                schema_version=published_layout["schema_version"],
                revision=1,
                updated_by=request.user,
            )

        log_event(
            category="dashboard",
            message=f"{request.user.get_display_name()} published the Command Center team default.",
            team=request.team,
            user=request.user,
            metadata={"panel_count": len(published_layout["panels"])},
        )
    return _resolution_response(request.team, request.user)


@require_permission("manage_team")
@require_POST
def remove_team_default(request, team_slug):
    _require_feature(request)
    try:
        payload = _json_payload(request)
        base_revision = _base_revision(payload)
    except LayoutValidationError as exc:
        return _error(str(exc))

    with transaction.atomic():
        team_default = (
            CommandCenterLayout.objects.select_for_update()
            .filter(team=request.team, scope=CommandCenterLayout.Scope.TEAM_DEFAULT)
            .first()
        )
        current_revision = team_default.revision if team_default else 0
        if base_revision != current_revision:
            return _error(
                "The team default changed in another browser tab. Reload before removing it.",
                status=409,
                code="revision_conflict",
            )
        if team_default:
            team_default.delete()
            log_event(
                category="dashboard",
                message=f"{request.user.get_display_name()} removed the Command Center team default.",
                team=request.team,
                user=request.user,
            )
    return _resolution_response(request.team, request.user)
