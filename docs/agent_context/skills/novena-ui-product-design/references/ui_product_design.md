# UI Product Design Reference

## Stack
- Django templates.
- HTMX for server-rendered partial updates.
- Alpine.js for local UI state.
- Tailwind CSS and DaisyUI.
- Chart.js for telemetry charts.

Do not assume React is available in Hub UI work.

## Product UX Principles
- Operational tools should be quiet, readable, and action-oriented.
- Put current status and last-seen context close to the object name.
- Avoid showing Online without freshness context.
- Separate hardware health from browser delivery state.
- Prefer customer-safe labels like Live - updated 4s ago, Delayed - last sample 42s ago, and Gateway online - device offline.

## Component Patterns
- Use compact cards for repeated items, metrics, and framed tools.
- Use full-width bands or unframed layouts for page sections.
- Use tables for operational history and telemetry samples.
- Keep chart areas and tables bounded so live data does not flood the page.
- Put units in labels or headers, not repeated in every cell.

## HTMX And Alpine
- Use HTMX for backend-owned state, partial refreshes, and form submissions.
- Use Alpine for local interaction state such as tabs, dropdowns, modals, and transient controls.
- Return app partials from templates/{app}/partials/ when an existing app pattern supports it.
- Use HX-Trigger only when another region must refresh after a successful action.

## Visual Style
- Prefer DaisyUI semantic classes and existing local patterns.
- Use responsive grid/flex layouts.
- Avoid fixed widths and heights unless a fixed-format UI element needs stable dimensions.
- Use clear buttons, icon buttons, toggles, tabs, menus, and selectors according to expected control behavior.

## Device Page Guidance
- Charts and live metric cards come before raw samples.
- Live samples tables should appear directly below charts.
- Command audit/history belongs near device identity or controls, not in the main telemetry reading flow.
- Browser stream badges should say whether the page is using WebSocket or polling fallback.
