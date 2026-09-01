# Telemetry Retention Policy

Novena uses two different retention concepts, and they are intentionally not the same thing.

## Customer-Visible History

Subscription plans control how much telemetry history a customer can view, query, export, and use in normal dashboard flows.

- Starter/unsubscribed default: 7 days.
- Business: 30 days.
- Enterprise/default upper tier: 90 days, unless a custom contract says otherwise.

If a customer downgrades, this visible history window shrinks immediately. For example, a team moving from Business to Starter should stop seeing data older than 7 days as soon as the active subscription changes.

If a customer upgrades, the visible history window expands immediately. Previously stored telemetry that is still inside the upgraded plan window can become visible.

## Physical Database Retention

Telemetry rows may remain in PostgreSQL/TimescaleDB after they fall outside a lower plan's visible history window. This is intentional product behavior, not a bug.

The current global physical retention policy is 90 days for raw telemetry and the hourly telemetry aggregate. TimescaleDB drops data after that global window. Until then, Novena may retain rows internally for operational continuity, upgrade recovery, diagnostics, and support.

In practical terms:

- A lower-tier customer can only view/query/export telemetry within their plan window.
- Older telemetry may still exist in the database until the global 90-day physical retention policy removes it.
- Upgrades may reveal retained telemetry within the newly allowed plan window.
- Downgrades immediately reduce access, but do not require immediate physical deletion of rows unless those rows exceed the global retention window.

Teacher note: think of the plan limit as the front door, and the database retention policy as the warehouse cleanup schedule. The front door can open wider or narrower immediately when the subscription changes. The warehouse cleanup still runs on its own global schedule.
