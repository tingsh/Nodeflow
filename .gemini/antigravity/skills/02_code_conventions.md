# Skill: Code Conventions & Patterns

## Metadata
- **ID:** 02_code_conventions
- **Description:** Prescriptive coding standards for models, views, templates, and the Nodeflow service layer.
- **Scope:** Use this skill for any code modification or new feature development to ensure 100% consistency with established patterns.

---

## 1. Django Models
- **Inheritance:** Always extend `BaseTeamModel` from `apps.teams.models` for tenant-aware models.
- **Choices:** Use `django.utils.translation.gettext_lazy` for choice labels. Define choices as class-level attributes.
- **Naming:** Use descriptive field names. Boolean fields should start with `is_` or `has_`.
- **JSON:** Use `JSONField` for flexible metadata or device-specific configurations.

## 2. Views & Permissions
- **CRUD:** Use Class-Based Views (CBVs) for standard CRUD. Mix in `PermissionRequiredMixin`.
- **HTMX/API:** Use Function-Based Views (FBVs) for simple partial swaps or API endpoints. Decorate with `@require_permission('permission_name')`.
- **RBAC:** We use a 5-tier system: `owner`, `admin`, `manager`, `operator`, `viewer`.
- **URL Parameters:** Always include `team_slug` as the first parameter.

## 3. Frontend Patterns (HTMX & Alpine.js)
- **HTMX Swaps:** Return rendered partials from `templates/{app}/partials/`.
- **Swapping Strategy:** Default to `hx-swap="innerHTML"`. Use `hx-target` to target specific containers.
- **Triggers:** Use `HX-Trigger` response headers to refresh other parts of the UI (e.g., updating a KPI card after a form save).
- **Alpine.js:** Use for local UI state only (modals, dropdowns, tab switching). Complex state stays in the backend via HTMX.

## 4. Service Layer
- All business logic MUST reside in `apps/{app}/services.py`.
- Services should be clean functions that take models or primitive types as arguments.
- Example: `create_alert_from_telemetry(telemetry_data)` rather than putting that logic in `Telemetry.save()`.

## 5. UI Styling (Tailwind & DaisyUI)
- **Colors:** Use DaisyUI semantic classes (`primary`, `secondary`, `accent`, `info`, `success`, `warning`, `error`).
- **Typography:** Use semantic HTML tags (`h1`, `h2`, `p`, `span`).
- **Layout:** Use Flexbox and CSS Grid. Avoid fixed widths/heights where possible to ensure responsiveness.

## 6. Logging & Error Handling
- **Logger:** Use `logger = logging.getLogger("iot_platform")`.
- **User Feedback:** Return an `alert-error` component via HTMX for validation failures.
- **Audit:** Critical operations (deletions, configuration changes) should be logged to the database for audit trails.
