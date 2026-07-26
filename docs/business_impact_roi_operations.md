# Business Impact and ROI Operations

## Purpose and Release Scope

Business Impact translates customer-authorized Hub data into measured operational outcomes, estimated opportunities, and estimated realized value. It is deliberately separate from ordinary telemetry monitoring: ambiguous datapoints can still appear on engineering dashboards, but they cannot create financial estimates.

Release 1 is Hub-only and supports:

- Factory energy.
- Cold chain.
- Facilities and HVAC, including hotels.

Solar and general-operations presets remain a later release. The Gateway payload, MQTT topics, and telemetry keys are unchanged.

The feature is controlled by the Waffle flag `business_impact_roi`. It is a technical rollout flag, not a paid-plan entitlement.

## Evidence Model

Each metric carries one of three evidence classes:

- **Measured:** a direct operational quantity, such as recorded labor minutes.
- **Calculated:** a deterministic result derived from measured data, such as integrated kWh.
- **Estimated:** a financial or avoided-risk interpretation that depends on assumptions or a baseline.

Release 1 never calls a result a “verified saving.” Every durable snapshot also retains its unit, currency, coverage, confidence, methodology version, assumption revision, warnings, and calculation breakdown.

Financial values are suppressed below 80% data coverage. Values from 80% up to 95% coverage are low-confidence; values at or above 95% receive normal confidence. Unknown or expired temperature calibration lowers confidence and creates a report warning. Novena monitors against the customer’s configured target and does not claim regulatory certification.

## Source Trust and Meter Topology

Only datapoints from verified device templates are suggested as Business Impact sources. A customer must confirm the source before calculation.

Energy sources have an explicit topology role:

- Site boundary/main meter.
- Submeter.
- Generation meter.
- Independent equipment meter.
- Monitoring only/excluded.

A confirmed boundary meter takes precedence over every downstream meter for site totals. If no boundary meter exists, only customer-selected, non-overlapping submeters or independent meters are added, and the result carries a warning. This is the control that prevents a main meter and its submeters from being counted twice.

The normalized datapoint schema is version 2. It adds physical quantity, aggregation behavior, canonical unit, conversion factor, counter behavior, expected interval, plausibility bounds, and supported impact roles. Semantically ambiguous datapoints remain usable for monitoring but not financial calculations.

## Calculation Method

Energy calculations prefer cumulative-counter deltas. The engine removes duplicate and out-of-order intervals, detects resets and configured rollovers, rejects implausible values, and excludes excessive sample gaps. Instantaneous power falls back to bounded trapezoidal integration. Peak demand uses fifteen-minute buckets.

Operating schedules are evaluated in each site’s timezone and support midnight-spanning windows, weekends, and date-specific overrides. After-hours and abnormal-load estimates are de-duplicated by using the larger overlapping opportunity rather than adding both.

Rolling baselines use up to four complete weeks of finalized local-day snapshots, require at least fourteen good-coverage days, and preserve comparable weekday averages. A customer-supplied monthly baseline can be used for an immediate pilot and is labeled as customer supplied. Recalculation creates a new snapshot or report revision; an issued report’s frozen payload never changes.

All money arithmetic uses `Decimal`. Currencies are never converted or combined.

## ROI Formulas

For one month:

```text
investment cost =
  active subscription cost
  + manual recurring service cost
  + one-time implementation cost / amortization months

estimated business value =
  baseline-supported energy reduction
  + eligible estimated risk reduction
  + baseline-supported downtime reduction
  + baseline-supported labor reduction

net benefit = estimated business value - investment cost

estimated ROI = net benefit / investment cost * 100
```

Payback is shown only when estimated realized value exceeds ongoing monthly cost. ROI is withheld when investment is zero, currencies conflict, coverage is insufficient, or a required assumption/baseline is missing. Open estimated opportunity is always shown separately and never inflates estimated realized ROI.

## Scheduled Work and Idempotency

Celery Beat dispatches:

- Hourly current-period refresh.
- Hourly local-time checks for previous-day finalization.
- Six-hour checks for prior-month report generation.
- Daily 24-month snapshot/report cleanup.

Source confirmation queues up to 90 days of retained telemetry backfill. Calculation takes a per-site database row lock, and snapshot/report uniqueness includes period, source, methodology, and revision. Overlapping jobs therefore update an unfinalized result or produce an explicit finalized revision rather than silently double-counting.

Monthly report email is opt-in. Email contains an authenticated Hub link and never attaches the confidential PDF. Tracked-delivery metadata supplies an idempotency key and preserves retry evidence.

## Private Report Storage

Local production reports use the `impact_reports` storage alias rooted at `/code/private_media`, outside the public `/media/` Nginx namespace. The web and Celery worker share the mounted directory. Prepare it before the first deployment and make it writable by the container’s `django` user.

S3 deployments use `PrivateMediaStorage`: private ACLs, no custom public domain, and signed query support. Application downloads still pass through tenant- and site-authorized Django views. Filenames contain internal numeric identifiers rather than customer names.

The database and report files form one logical backup:

- `backup_postgres.sh` preserves report metadata and frozen payloads.
- `backup_private_media.sh` preserves local PDFs.
- `backup_retention.sh` applies daily, weekly, and monthly retention to both.

Follow `docs/production_backup_restore.md` for the paired restore drill. For S3, use private bucket versioning and a separate backup policy.

## Deployment

1. Build the production image so WeasyPrint and its Pango/Cairo libraries are present.
2. Create and permission `private_media`; never add it to an Nginx public alias.
3. Apply migrations. The data migration creates team and site impact profiles, enables only the three Release 1 presets, and seeds revision 1 assumptions without inventing tariffs or savings.
4. Run `python manage.py production_readiness_check`. Private storage and PDF import must report `OK`.
5. Start web, worker, and Beat. Confirm all four Business Impact scheduled tasks are registered.
6. Create `business_impact_roi` in Waffle with `everyone=False`.
7. Enable the flag for an internal team, confirm source topology and assumptions, then queue historical backfill.
8. Validate factory, cold-chain, and facilities golden datasets and a private report download with every role.
9. Expand to a small customer-authorized canary. Enable `everyone=True` only after acceptance evidence is complete.

Rollback by disabling the flag first. Existing snapshots and reports are retained. Reverting application code requires reviewing the applied migrations; do not drop impact tables during an operational rollback.

## Monitoring and SLOs

Alert on:

- Site calculation errors or repeated Celery retries.
- Coverage below 80% for a previously healthy site.
- Unknown/expired cold-chain calibration.
- Failed report generations or tracked email deliveries.
- Missing private files for ready report rows.
- Monthly generation success below 99%.
- Business Impact dashboard response above two seconds at the canary cohort size.

Financial golden datasets must match within normal currency-rounding tolerance. A support investigation should begin from the report/snapshot breakdown and its exact assumption revision, then inspect source mapping, calibration, coverage, counter warnings, and baseline revision in that order.
