# WhatsApp Integration Setup Guide

This guide covers the Novena Hub WhatsApp integration for alert notifications and the maintenance reply loop.

## What Is Already Wired In Code

Novena Hub already has the main application hooks:

- Alert rules can enable `notify_whatsapp`.
- Alert notifications dispatch through Celery via `dispatch_alert_whatsapp_task`.
- Maintenance ticket assignments can notify assignees on WhatsApp.
- Incoming WhatsApp messages are routed to `/maintenance/whatsapp/webhook/`.
- Technicians can reply with commands such as `LIST`, `DONE 1`, `TKT-123 DONE 1`, and `STATUS Resolved`.

The missing part is mostly configuration in Meta/WhatsApp Business and runtime environment variables.

## Important WhatsApp Rule

The current code sends WhatsApp Cloud API `text` messages.

That is useful for development, local mock logs, and replies inside an active customer-service conversation window. For production business-initiated alert pushes, WhatsApp commonly requires pre-approved message templates. If Meta rejects outbound alert texts even though the token and phone number ID are correct, this is likely a template/window issue rather than a Django bug.

We should first complete Cloud API setup and verify inbound/outbound plumbing. After that, create approved alert and maintenance templates in Meta and wire template sending if needed.

## Meta / WhatsApp Business Tasks

Do these in Meta Business Manager and the Meta Developer dashboard.

1. Create or select the Meta Business account for Novena.
2. Create or select a Meta app with WhatsApp enabled.
3. Add a WhatsApp Business Account and phone number.
4. Copy the Phone Number ID. This is not the visible phone number; it is the numeric Cloud API ID used in the `/messages` endpoint.
5. Create a permanent access token for production use.
6. Ensure the token can use WhatsApp messaging permissions:
   - `whatsapp_business_messaging`
   - `whatsapp_business_management`
7. Configure the webhook callback URL:

   ```text
   https://<your-public-novena-domain>/maintenance/whatsapp/webhook/
   ```

8. Set a strong webhook verify token in Meta. This must exactly match `WHATSAPP_VERIFY_TOKEN` in Novena.
9. Subscribe the webhook to WhatsApp message events.
10. Add test recipient phone numbers while still in Meta test mode. For production, complete business/phone verification and any required display-name approval.

## Novena Environment Variables

Set these in the environment where Django and Celery run:

```env
WHATSAPP_PROVIDER="meta"
WHATSAPP_GRAPH_API_VERSION="v21.0"
WHATSAPP_PHONE_NUMBER_ID="<meta-phone-number-id>"
WHATSAPP_ACCESS_TOKEN="<meta-access-token>"
WHATSAPP_VERIFY_TOKEN="<same-token-entered-in-meta-webhook-config>"
APP_BASE_URL="https://<your-public-novena-domain>"
```

For local development without sending real WhatsApp messages:

```env
WHATSAPP_PROVIDER="mock"
```

`mock` mode logs messages instead of calling Meta. This is the safest mode when testing alert-rule behavior locally.

## Public URL Requirement

Meta must reach the webhook over a public HTTPS URL. `localhost:8000` will not work for webhook verification.

For staging or production, use the real Novena domain. For temporary local testing, use a tunnel such as ngrok or Cloudflare Tunnel and set:

```env
APP_BASE_URL="https://<temporary-public-tunnel-domain>"
```

Then enter this callback in Meta:

```text
https://<temporary-public-tunnel-domain>/maintenance/whatsapp/webhook/
```

## Novena App Setup

1. Restart Django after changing env vars.
2. Restart the Celery worker after changing env vars. Alert and maintenance WhatsApp sends happen in Celery tasks, so updating only Django is not enough.
3. In Novena, open the user profile or team member settings for each recipient.
4. Add WhatsApp numbers with country code, for example:

   ```text
   +6591234567
   ```

5. Create or update an alert rule.
6. Enable WhatsApp Push.
7. Select at least one recipient who has a phone number.
8. Trigger a test alert from telemetry or the simulator.
9. Check Celery logs for either a successful Meta send or a Meta API error response.

## Maintenance Reply Loop Test

After inbound webhooks are verified:

1. Assign a maintenance ticket to a user with a WhatsApp number.
2. Enable WhatsApp notification on that ticket.
3. Confirm the user receives the ticket assignment message.
4. From that WhatsApp account, reply:

   ```text
   LIST
   ```

5. For a ticket with checklist tasks, reply:

   ```text
   TKT-123 DONE 1
   ```

6. To change status, reply:

   ```text
   TKT-123 STATUS In Progress
   ```

Novena matches inbound messages to users by normalized phone number, so the sender phone in WhatsApp must match the phone number stored on the Novena user.

## Troubleshooting

- Webhook verification fails: `WHATSAPP_VERIFY_TOKEN` does not match the token entered in Meta, or Meta cannot reach the public HTTPS URL.
- Outbound sends log missing config: `WHATSAPP_PHONE_NUMBER_ID` or `WHATSAPP_ACCESS_TOKEN` is not present in the Celery worker environment.
- Outbound sends hit a Meta API error: check whether the recipient is allowed in test mode, whether the phone number is in international format, and whether a template is required.
- Inbound commands do nothing: confirm the webhook is subscribed to message events and the sender phone number matches a Novena user.
- Django works but sends still use old config: restart Celery.

## Next Production Hardening Step

Before using this for real customer alerting, create approved WhatsApp message templates for:

- Critical/warning alert triggered
- Alert resolved
- Maintenance ticket assigned

Once those templates are approved, wire Novena to send template messages for business-initiated notifications and keep free-form text for technician replies inside the active conversation window.

## Alert Template Expected By Novena

For end-to-end alert testing beyond Meta's `hello_world` sandbox template, create this WhatsApp template in Meta:

```text
Template name: novena_alert_notification
Category: Utility
Language: English (US) / en_US
```

Suggested body:

```text
Novena Alert {{1}}

Rule: {{2}}
Device: {{3}}
Value: {{4}}
Severity: {{5}}
Time: {{6}}

Open alerts: {{7}}
```

Novena maps the template variables as:

```text
{{1}} = alert status, for example CRITICAL or RESOLVED
{{2}} = alert rule name
{{3}} = device name
{{4}} = trigger value
{{5}} = severity
{{6}} = trigger timestamp
{{7}} = alert dashboard URL
```

After Meta approves the template, set:

```env
WHATSAPP_ALERT_TEMPLATE_NAME="novena_alert_notification"
WHATSAPP_ALERT_TEMPLATE_LANGUAGE="en_US"
```

## Official References

- Meta WhatsApp Cloud API: https://developers.facebook.com/docs/whatsapp/cloud-api/
- Meta WhatsApp Cloud API webhooks: https://developers.facebook.com/docs/whatsapp/cloud-api/webhooks/
- Meta Graph API versioning: https://developers.facebook.com/docs/graph-api/changelog/versions
