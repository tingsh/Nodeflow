# Novena Email Sender Strategy

This document plans the next polish pass for Novena's transactional email system after the initial Amazon SES setup. The current development milestone is complete: Novena can send real alert email through SES, and local delivery audit reaches `EmailDelivery.status = sent`.

## Current State

Novena currently uses one general sender for most transactional emails:

```env
DEFAULT_FROM_EMAIL="Novena Platform <no-reply@alerts.novenaplatform.com>"
SERVER_EMAIL="no-reply@alerts.novenaplatform.com"
CONTACT_EMAIL="support@novenaplatform.com"
```

That is acceptable for local development and early pre-production testing. It proves the core pipeline:

```text
Novena Hub -> django-anymail -> Amazon SES -> recipient inbox
```

The next polish pass should make sender identity explicit by email purpose.

## Recommended Sender Addresses

Use purpose-specific senders, but keep the system simple. These are transactional emails, not marketing newsletters.

| Purpose | Recommended sender | Reply-To | Notes |
| --- | --- | --- | --- |
| Alerts | `Novena Alerts <no-reply@alerts.novenaplatform.com>` | `support@novenaplatform.com` | Critical telemetry alerts, alert resolution notices. |
| Account/Auth | `Novena Accounts <no-reply@accounts.novenaplatform.com>` | `support@novenaplatform.com` | Password reset, email verification, account security notices. |
| Team/Admin | `Novena Platform <no-reply@notifications.novenaplatform.com>` | `support@novenaplatform.com` | Team invitations, membership changes, admin notices. |
| Billing | `Novena Billing <billing@novenaplatform.com>` | `billing@novenaplatform.com` | Payment failed, invoice, receipt, subscription changes. |
| Support | `Novena Support <support@novenaplatform.com>` | `support@novenaplatform.com` | Support request acknowledgements and support staff replies. |
| Maintenance | `Novena Maintenance <no-reply@maintenance.novenaplatform.com>` | `support@novenaplatform.com` | Ticket assignment, contractor updates, resolution notices. |
| System/Error | `Novena System <server@novenaplatform.com>` | `support@novenaplatform.com` | Django server/admin error email. |

Teacher note: the `From` address is the identity the mailbox sees as the sender. `Reply-To` is where replies should go. A `no-reply` sender can still have a useful `Reply-To`, which lets us preserve a clean sender identity while directing customer replies to the right team.

## Proposed Environment Variables

Add these to `.env.example` in the implementation pass:

```env
# General email
DEFAULT_FROM_EMAIL="Novena Platform <no-reply@notifications.novenaplatform.com>"
SERVER_EMAIL="Novena System <server@novenaplatform.com>"
CONTACT_EMAIL="support@novenaplatform.com"

# Purpose-specific transactional senders
ALERTS_FROM_EMAIL="Novena Alerts <no-reply@alerts.novenaplatform.com>"
ACCOUNTS_FROM_EMAIL="Novena Accounts <no-reply@accounts.novenaplatform.com>"
TEAM_FROM_EMAIL="Novena Platform <no-reply@notifications.novenaplatform.com>"
BILLING_FROM_EMAIL="Novena Billing <billing@novenaplatform.com>"
SUPPORT_FROM_EMAIL="Novena Support <support@novenaplatform.com>"
MAINTENANCE_FROM_EMAIL="Novena Maintenance <no-reply@maintenance.novenaplatform.com>"

# Reply destinations
SUPPORT_REPLY_TO_EMAIL="support@novenaplatform.com"
BILLING_REPLY_TO_EMAIL="billing@novenaplatform.com"
```

Do not add real secrets to `.env.example`. These sender values are not secrets, but they must be verified in SES before use.

## Email Types Novena Should Support

### Account And Security

- Password reset.
- Email verification.
- Account recovery.
- New login or suspicious login notice.
- Password changed.
- User invited to team.
- Team role changed.
- Team deleted or scheduled for closure.

### Alerts And Operations

- Alert triggered.
- Alert resolved.
- Escalation notice.
- Alert delivery failure summary for admins.
- Device/gateway offline notice.
- Gateway reconnected notice.
- Sensor stale-data notice.

### Maintenance

- Ticket assigned.
- Ticket commented on.
- Ticket resolved.
- Contractor link shared.
- Preventive maintenance due soon.
- Preventive maintenance overdue.

### Billing And Subscription

- Checkout/session confirmation.
- Invoice available.
- Payment succeeded.
- Payment failed.
- Subscription upgraded/downgraded/cancelled.
- Trial ending soon.
- Usage or limit warning.

### Support And Sales

- Support request acknowledgement to customer.
- Support request notification to Novena staff.
- Sales/demo inquiry acknowledgement.
- Sales/demo inquiry notification to Novena staff.

## Implementation Plan

### 1. Add Typed Sender Settings

Add settings in `novena_hub/settings.py`:

```python
ALERTS_FROM_EMAIL = env("ALERTS_FROM_EMAIL", default=DEFAULT_FROM_EMAIL)
ACCOUNTS_FROM_EMAIL = env("ACCOUNTS_FROM_EMAIL", default=DEFAULT_FROM_EMAIL)
TEAM_FROM_EMAIL = env("TEAM_FROM_EMAIL", default=DEFAULT_FROM_EMAIL)
BILLING_FROM_EMAIL = env("BILLING_FROM_EMAIL", default=DEFAULT_FROM_EMAIL)
SUPPORT_FROM_EMAIL = env("SUPPORT_FROM_EMAIL", default=DEFAULT_FROM_EMAIL)
MAINTENANCE_FROM_EMAIL = env("MAINTENANCE_FROM_EMAIL", default=DEFAULT_FROM_EMAIL)
SUPPORT_REPLY_TO_EMAIL = env("SUPPORT_REPLY_TO_EMAIL", default=PROJECT_METADATA["CONTACT_EMAIL"])
BILLING_REPLY_TO_EMAIL = env("BILLING_REPLY_TO_EMAIL", default=PROJECT_METADATA["CONTACT_EMAIL"])
```

### 2. Extend The Tracked Email Service

Update `send_tracked_email(...)` to accept:

```python
reply_to=None
```

and pass it into `AnymailMessage(reply_to=[...])` when provided.

Consider adding these fields to `EmailDelivery`:

```text
from_email
reply_to
subject
```

That gives support staff better evidence when a customer asks, "Who did this email come from?"

### 3. Route Each Email Type Through The Correct Sender

Update code paths:

- Alerts: use `settings.ALERTS_FROM_EMAIL`.
- Alert resolution: use `settings.ALERTS_FROM_EMAIL`.
- Team invitations: use `settings.TEAM_FROM_EMAIL`.
- Maintenance assignment/resolution: use `settings.MAINTENANCE_FROM_EMAIL`.
- Support form staff notification: use `settings.SUPPORT_FROM_EMAIL`, reply-to customer email.
- Sales inquiry staff notification: use `settings.SUPPORT_FROM_EMAIL`, reply-to prospect email.
- Billing emails: use `settings.BILLING_FROM_EMAIL`.
- Password/account emails: configure allauth/Django templates to use `settings.ACCOUNTS_FROM_EMAIL` where possible, or use `DEFAULT_FROM_EMAIL` until the account-email pass.

### 4. Standardize Email Metadata

Every tracked email should include metadata:

```json
{
  "notification_type": "...",
  "team_id": "...",
  "user_id": "...",
  "source": "novena_hub"
}
```

For billing emails, include Stripe invoice/subscription ids when available.

### 5. Template Polish

Create consistent email partials for:

- header,
- severity/status badge,
- primary CTA button,
- footer,
- support contact line.

Avoid making the email feel like marketing. These are operational messages; clarity matters more than flourish.

### 6. Tests

Add focused tests that verify:

- alert emails use `ALERTS_FROM_EMAIL`;
- invitation emails use `TEAM_FROM_EMAIL`;
- support inquiries use `SUPPORT_FROM_EMAIL` and reply-to the customer;
- maintenance emails use `MAINTENANCE_FROM_EMAIL`;
- billing emails use `BILLING_FROM_EMAIL`;
- `EmailDelivery` stores sender and subject if those fields are added;
- missing optional sender settings fall back to `DEFAULT_FROM_EMAIL`.

## AWS SES Configuration Guide For Purpose-Specific Senders

### Development

For local development, it is enough to verify each exact sender you want to test:

```text
no-reply@alerts.novenaplatform.com
support@novenaplatform.com
billing@novenaplatform.com
```

If SES is still in sandbox mode, also verify every recipient address used for testing.

### Production

For production, prefer domain identities over many individual email identities:

```text
novenaplatform.com
alerts.novenaplatform.com
accounts.novenaplatform.com
notifications.novenaplatform.com
maintenance.novenaplatform.com
```

AWS SES domain verification allows sending from addresses under a verified domain, but advanced sending features such as configuration sets may require explicit email identity verification in some cases. If a sender fails after we enable configuration sets, explicitly verify that exact sender address too.

### DNS Records

For each SES domain identity:

1. Enable Easy DKIM.
2. Add the SES DKIM CNAME records to DNS.
3. Wait until SES shows the identity as verified.
4. Add or verify SPF/DMARC records for the domain.
5. For production polish, configure a custom MAIL FROM domain.

Recommended DMARC starting point:

```text
v=DMARC1; p=none; rua=mailto:dmarc@novenaplatform.com
```

Later, after monitoring legitimate delivery, move toward stricter policy:

```text
v=DMARC1; p=quarantine; rua=mailto:dmarc@novenaplatform.com
```

### IAM

The local IAM user only needs sending permission:

```json
{
  "Effect": "Allow",
  "Action": [
    "ses:SendEmail",
    "ses:SendRawEmail"
  ],
  "Resource": "*"
}
```

In production, prefer an IAM role attached to the runtime instead of static access keys.

### Production Event Tracking Later

When Novena is publicly hosted on HTTPS, complete the deferred production tracking setup:

1. Request SES production access.
2. Create SES configuration set, for example `novena-prod-email`.
3. Create SNS topic for SES events.
4. Subscribe SNS to:

   ```text
   https://<username>:<password>@<novena-domain>/anymail/amazon_ses/tracking/
   ```

5. Enable SES events: send, delivery, bounce, complaint, reject, rendering failure, delivery delay.
6. Set:

   ```env
   AWS_SES_CONFIGURATION_SET_NAME="novena-prod-email"
   ANYMAIL_WEBHOOK_SECRET="<username>:<password>"
   ```

## References

- AWS SES identities: https://docs.aws.amazon.com/ses/latest/dg/creating-identities.html
- AWS SES event publishing: https://docs.aws.amazon.com/ses/latest/dg/monitor-using-event-publishing.html
- Anymail Amazon SES: https://anymail.dev/en/v13.0/esps/amazon_ses/
