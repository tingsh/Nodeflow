from __future__ import annotations

from copy import deepcopy

from .models import CommandCenterLayout

SCHEMA_VERSION = 1
GRID_COLUMNS = 12
MAX_GRID_ROW = 200

PANEL_REGISTRY = {
    "business_impact": {
        "title": "Business Impact",
        "description": "Operational value, opportunity, cost, net benefit, and ROI.",
        "default": {"x": 0, "y": 0, "w": 12, "h": 2},
        "min": {"w": 6, "h": 2},
        "max": {"w": 12, "h": 4},
        "hideable": True,
        "requires_impact": True,
    },
    "operations_trend": {
        "title": "Operations Trend",
        "description": "A 24-hour view of the most relevant operational signal.",
        "default": {"x": 0, "y": 2, "w": 8, "h": 4},
        "min": {"w": 6, "h": 3},
        "max": {"w": 12, "h": 6},
        "hideable": True,
    },
    "needs_attention": {
        "title": "Needs Attention",
        "description": "Device, gateway, alert, and maintenance exceptions requiring review.",
        "default": {"x": 8, "y": 2, "w": 4, "h": 4},
        "min": {"w": 4, "h": 3},
        "max": {"w": 12, "h": 6},
        "hideable": True,
        "warn_before_hide": True,
    },
    "asset_mix": {
        "title": "Asset Mix",
        "description": "The types of monitored equipment in this fleet.",
        "default": {"x": 0, "y": 6, "w": 4, "h": 4},
        "min": {"w": 3, "h": 3},
        "max": {"w": 6, "h": 6},
        "hideable": True,
    },
    "device_fleet": {
        "title": "Device Fleet",
        "description": "Freshness and latest readings for priority devices.",
        "default": {"x": 4, "y": 6, "w": 4, "h": 5},
        "min": {"w": 4, "h": 3},
        "max": {"w": 8, "h": 7},
        "hideable": True,
    },
    "sites_actions": {
        "title": "Sites & Actions",
        "description": "Site-level fleet status and common setup actions.",
        "default": {"x": 8, "y": 6, "w": 4, "h": 5},
        "min": {"w": 4, "h": 3},
        "max": {"w": 8, "h": 7},
        "hideable": True,
    },
}


class LayoutValidationError(ValueError):
    pass


def novena_default_layout():
    panels = []
    for mobile_order, (panel_id, definition) in enumerate(PANEL_REGISTRY.items()):
        panels.append(
            {
                "id": panel_id,
                **deepcopy(definition["default"]),
                "hidden": False,
                "mobile_order": mobile_order,
            }
        )
    return {"schema_version": SCHEMA_VERSION, "panels": panels}


def available_panel_ids(*, include_impact):
    return {
        panel_id
        for panel_id, definition in PANEL_REGISTRY.items()
        if include_impact or not definition.get("requires_impact")
    }


def normalize_layout(layout):
    defaults = novena_default_layout()
    if not isinstance(layout, dict) or layout.get("schema_version") != SCHEMA_VERSION:
        return defaults

    stored = {}
    for panel in layout.get("panels", []):
        if isinstance(panel, dict) and panel.get("id") in PANEL_REGISTRY:
            stored[panel["id"]] = panel

    normalized = []
    for fallback in defaults["panels"]:
        panel_id = fallback["id"]
        candidate = stored.get(panel_id, fallback)
        definition = PANEL_REGISTRY[panel_id]
        try:
            entry = {
                "id": panel_id,
                "x": int(candidate["x"]),
                "y": int(candidate["y"]),
                "w": int(candidate["w"]),
                "h": int(candidate["h"]),
                "hidden": bool(candidate.get("hidden", False)),
                "mobile_order": int(candidate.get("mobile_order", fallback["mobile_order"])),
            }
        except (KeyError, TypeError, ValueError):
            entry = fallback

        minimum = definition["min"]
        maximum = definition["max"]
        if not (
            0 <= entry["x"] < GRID_COLUMNS
            and 0 <= entry["y"] <= MAX_GRID_ROW
            and minimum["w"] <= entry["w"] <= maximum["w"]
            and minimum["h"] <= entry["h"] <= maximum["h"]
            and entry["x"] + entry["w"] <= GRID_COLUMNS
        ):
            entry = fallback
        normalized.append(entry)

    normalized.sort(key=lambda panel: panel["mobile_order"])
    for mobile_order, panel in enumerate(normalized):
        panel["mobile_order"] = mobile_order
    return {"schema_version": SCHEMA_VERSION, "panels": normalized}


def resolve_layout(team, user):
    personal = CommandCenterLayout.objects.filter(
        team=team,
        user=user,
        scope=CommandCenterLayout.Scope.PERSONAL,
    ).first()
    team_default = CommandCenterLayout.objects.filter(
        team=team,
        scope=CommandCenterLayout.Scope.TEAM_DEFAULT,
    ).first()

    source_record = personal or team_default
    return {
        "layout": normalize_layout(source_record.layout if source_record else None),
        "source": (
            CommandCenterLayout.Scope.PERSONAL
            if personal
            else CommandCenterLayout.Scope.TEAM_DEFAULT
            if team_default
            else "novena_default"
        ),
        "revision": source_record.revision if source_record else 0,
        "personal_revision": personal.revision if personal else 0,
        "team_default_revision": team_default.revision if team_default else 0,
    }


def panel_context(resolved_layout, *, include_impact):
    available = available_panel_ids(include_impact=include_impact)
    panels = []
    for entry in resolved_layout["panels"]:
        if entry["id"] not in available:
            continue
        definition = PANEL_REGISTRY[entry["id"]]
        panels.append({**entry, **definition})
    return panels


def client_config(resolution, *, include_impact, can_publish, urls):
    available = available_panel_ids(include_impact=include_impact)
    catalog = []
    for panel_id, definition in PANEL_REGISTRY.items():
        if panel_id not in available:
            continue
        catalog.append(
            {
                "id": panel_id,
                "title": definition["title"],
                "description": definition["description"],
                "min": definition["min"],
                "default": definition["default"],
                "max": definition["max"],
                "hideable": definition["hideable"],
                "warn_before_hide": definition.get("warn_before_hide", False),
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "layout": resolution["layout"],
        "source": resolution["source"],
        "personal_revision": resolution["personal_revision"],
        "team_default_revision": resolution["team_default_revision"],
        "can_publish": can_publish,
        "catalog": catalog,
        "urls": urls,
    }


def validate_layout_payload(payload, *, available_ids, base_layout):
    if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA_VERSION:
        raise LayoutValidationError("Unsupported layout schema.")
    submitted = payload.get("panels")
    if not isinstance(submitted, list) or len(submitted) > len(PANEL_REGISTRY):
        raise LayoutValidationError("Panels must be a bounded list.")

    submitted_by_id = {}
    allowed_keys = {"id", "x", "y", "w", "h", "hidden", "mobile_order"}
    for raw in submitted:
        if not isinstance(raw, dict) or set(raw) - allowed_keys:
            raise LayoutValidationError("A panel contains unsupported fields.")
        panel_id = raw.get("id")
        if panel_id not in PANEL_REGISTRY or panel_id in submitted_by_id:
            raise LayoutValidationError("Panel identifiers must be known and unique.")
        for key in ("x", "y", "w", "h", "mobile_order"):
            if not isinstance(raw.get(key), int) or isinstance(raw.get(key), bool):
                raise LayoutValidationError("Panel coordinates and sizes must be integers.")
        if not isinstance(raw.get("hidden"), bool):
            raise LayoutValidationError("Panel visibility must be a boolean.")

        definition = PANEL_REGISTRY[panel_id]
        if not (
            0 <= raw["x"] < GRID_COLUMNS
            and 0 <= raw["y"] <= MAX_GRID_ROW
            and definition["min"]["w"] <= raw["w"] <= definition["max"]["w"]
            and definition["min"]["h"] <= raw["h"] <= definition["max"]["h"]
            and raw["x"] + raw["w"] <= GRID_COLUMNS
            and 0 <= raw["mobile_order"] < len(PANEL_REGISTRY)
        ):
            raise LayoutValidationError(f"Panel geometry is invalid for {panel_id}.")
        submitted_by_id[panel_id] = deepcopy(raw)

    if not available_ids.issubset(submitted_by_id):
        raise LayoutValidationError("Every available panel must be included.")
    mobile_orders = [submitted_by_id[panel_id]["mobile_order"] for panel_id in available_ids]
    if len(mobile_orders) != len(set(mobile_orders)):
        raise LayoutValidationError("Mobile panel order must be unique.")

    visible = [submitted_by_id[panel_id] for panel_id in available_ids if not submitted_by_id[panel_id]["hidden"]]
    for index, left in enumerate(visible):
        for right in visible[index + 1 :]:
            overlaps = not (
                left["x"] + left["w"] <= right["x"]
                or right["x"] + right["w"] <= left["x"]
                or left["y"] + left["h"] <= right["y"]
                or right["y"] + right["h"] <= left["y"]
            )
            if overlaps:
                raise LayoutValidationError("Visible panels cannot overlap.")

    merged = {panel["id"]: panel for panel in normalize_layout(base_layout)["panels"]}
    merged.update(submitted_by_id)
    panels = list(merged.values())
    panels.sort(key=lambda panel: panel["mobile_order"])
    return {"schema_version": SCHEMA_VERSION, "panels": panels}
