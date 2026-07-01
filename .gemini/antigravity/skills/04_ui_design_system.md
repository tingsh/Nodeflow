# Skill: UI/UX Design System

## Metadata
- **ID:** 04_ui_design_system
- **Description:** Prescriptive design tokens, component patterns, and visual aesthetics for the Novena "Command Center" interface.
- **Scope:** Use this skill for any frontend work, including new dashboard widgets, marketing pages, or operational forms.

---

## 1. The "Rich Aesthetics" Identity
Novena follows a "Command Center" aesthetic:
- **Primary Palette:** Slate, Indigo, and Emerald.
- **Dark Mode:** Deep slate backgrounds (`bg-base-300`) with subtle textural grain.
- **Visual Depth:** Use glassmorphism (blur + border glow) for primary dashboard cards.
- **Micro-interactions:** Subtle hover scales and AOS.js (Animate On Scroll) for marketing sections.

## 2. Component Patterns

### KPI Cards (Stat Boxes)
- **Container:** `card bg-base-200 shadow-xl border border-base-content/10`.
- **Content:** Icon (top-left), Label (gray-text), Value (bold primary), Trend indicator (small green/red badge).
- **Update Logic:** Use HTMX polling or WebSocket updates to keep values live.

### Data Tables
- **Container:** `overflow-x-auto`.
- **Table:** `table table-zebra w-full`.
- **Actions:** Use a "three-dot" dropdown for row-specific operations (Edit, Delete, Control).

### Forms
- **Standard:** DaisyUI `form-control` with `input-bordered`.
- **Feedback:** Use `label-text-alt text-error` for validation messages.
- **Loading:** Always add an `htmx-indicator` (spinner or pulse) to submit buttons.

## 3. Real-Time Indicators
- **Online Dot:** `badge-success badge-xs` (pulsing).
- **Offline Dot:** `badge-ghost badge-xs`.
- **Alarm State:** `badge-error animate-pulse`.

## 4. Charts (Chart.js)
- **Line Charts:** Use for telemetry. Tension: 0.4 (curved), Point Radius: 0.
- **Colors:** Primary (Indigo), Secondary (Emerald), Danger (Rose).
- **Grid:** Hide grid lines on X-axis; keep horizontal grid lines subtle (`rgba(255, 255, 255, 0.1)`).

## 5. Responsive Breakpoints
- **Mobile:** Single column, hidden sidebar (drawer toggle).
- **Tablet:** Two-column grid, collapsed sidebar icons.
- **Desktop:** Multi-column Bento grid, full sidebar.

## 6. Iconography
- Use **Lucide React** or standard SVG icons.
- Icons should be consistent in weight (thin) and color (primary-content/70).
