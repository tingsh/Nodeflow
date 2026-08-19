# Amazon SES Setup Guide

This guide configures Amazon SES for local Novena Hub development so we can test transactional email sending for SaaS flows such as password reset, team invitations, and alert notifications.

Novena is currently running on a local machine, so skip the production-only pieces for now:

- SES production access
- SNS subscription to Novena
- SES event publishing to SNS
- bounce and complaint webhook verification
- CloudWatch production reputation alarms

Those pieces require Novena Hub to be hosted on a public HTTPS domain so AWS can call back into `/anymail/amazon_ses/tracking/`.

## Production Revisit Note

When Novena Hub moves from local development to a public hosted environment, revisit this SES setup before launch. At that point, complete and test the pieces that require a public-facing HTTPS site:

1. Request SES production access.
2. Create production SES configuration set event publishing.
3. Create the SNS topic for SES delivery events.
4. Subscribe SNS to Novena's public Anymail tracking endpoint.
5. Confirm SNS can reach `/anymail/amazon_ses/tracking/`.
6. Test bounce, complaint, reject, delivery delay, and delivery events.
7. Verify `EmailDelivery` rows move beyond `sent` into final webhook-driven statuses.
8. Add CloudWatch/reputation monitoring for bounce and complaint rates.

Until then, local testing should focus on whether Novena can submit emails to SES successfully. In local development, `EmailDelivery.status = sent` means SES accepted the message; public webhook tracking is what later upgrades that audit trail to `delivered`, `bounced`, `complained`, or `rejected`.

## 1. Choose The SES Region

Use one SES region for development. For Singapore and ASEAN testing, use:

```env
AWS_SES_REGION_NAME="ap-southeast-1"
```

Make sure every SES identity and IAM permission you create is in the same region.

## 2. Create A Sender Identity

For local development, the fastest path is to verify one sender email address.

1. Open the AWS Console.
2. Go to Amazon SES.
3. Confirm you are in `ap-southeast-1`, unless you chose another region.
4. Open `Configuration -> Identities`.
5. Choose `Create identity`.
6. Select `Email address`.
7. Enter the sender address you want Novena to send from.
8. Open the verification email from AWS and confirm it.

If you already have access to the domain DNS, you can verify the whole domain instead. Domain verification is better for production because it supports DKIM and all senders under that domain.

## 3. Verify Test Recipients While In Sandbox

New SES accounts usually start in sandbox mode. Sandbox mode means SES only lets you send:

- from verified sender identities, and
- to verified recipient identities.

For development, verify the email address you want to receive test emails at:

1. In SES, open `Configuration -> Identities`.
2. Choose `Create identity`.
3. Select `Email address`.
4. Enter your test recipient email address.
5. Confirm the verification email.

This is why password reset or alert emails may fail during development if you send to an unverified recipient.

## 4. Create IAM Credentials For Local Sending

Because Novena Hub is running locally, it cannot use an AWS runtime role. Create an IAM user or access key with SES send permission.

Minimum sending policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ses:SendEmail",
        "ses:SendRawEmail"
      ],
      "Resource": "*"
    }
  ]
}
```

Keep the access key private. Do not commit it.

## 5. Configure Local `.env`

Set these in local `.env`:

```env
EMAIL_BACKEND="anymail.backends.amazon_ses.EmailBackend"
AWS_SES_REGION_NAME="ap-southeast-1"
AWS_SES_ACCESS_KEY_ID="<your-local-ses-access-key-id>"
AWS_SES_SECRET_ACCESS_KEY="<your-local-ses-secret-access-key>"
AWS_SES_CONFIGURATION_SET_NAME=""
ANYMAIL_WEBHOOK_SECRET=""
DEFAULT_FROM_EMAIL="Novena Platform <verified-sender@example.com>"
SERVER_EMAIL="verified-sender@example.com"
CONTACT_EMAIL="verified-sender@example.com"
```

For local development, keep these blank:

```env
AWS_SES_CONFIGURATION_SET_NAME=""
ANYMAIL_WEBHOOK_SECRET=""
```

`AWS_SES_CONFIGURATION_SET_NAME` is for SES event publishing. `ANYMAIL_WEBHOOK_SECRET` protects the public webhook endpoint. Neither is needed while Novena Hub is only available on localhost.

## 6. Restart Novena Services

Restart every process that sends email:

1. Django web server.
2. Celery worker.
3. Celery beat if it is running.

Changing `.env` only affects newly started processes. Celery is especially important because alert and invitation emails are sent in background tasks.

## 7. Run A Basic SES Smoke Test

From WSL:

```bash
cd /home/shouheng/Novena-Platform/Novena-Hub
source ~/.venvs/novena/bin/activate
DJANGO_SETTINGS_MODULE=novena_hub.settings python manage.py send_test_email verified-recipient@example.com
```

Use a verified recipient while SES is still in sandbox mode.

## 8. Test Password Reset Email

1. Start the local Django app.
2. Open the password reset page.
3. Enter an email address that exists in Novena and is also verified in SES.
4. Submit the form.
5. Confirm the reset email arrives.

If it does not arrive, check the Django logs for SES errors such as `MessageRejected`.

## 9. Test Alert Email

1. In Novena, create or edit an alert rule.
2. Enable email notification.
3. Select at least one recipient.
4. Make sure the recipient email is verified in SES while you are in sandbox mode.
5. Trigger telemetry that crosses the alert threshold.
6. Confirm:
   - an `Alert` row is created,
   - an `EmailDelivery` row is created,
   - the delivery status becomes `sent`,
   - the recipient receives the email.

Because SNS event publishing is not enabled locally, the delivery status will usually stop at `sent`. That means SES accepted the message for delivery. Later, when Novena has a public HTTPS domain, SNS webhooks can update the status to `delivered`, `bounced`, `complained`, or `rejected`.

## 10. What To Skip Until Public Hosting

Skip these until Novena Hub is deployed to a public HTTPS URL:

1. SES production access request.
2. SES configuration set event destination.
3. SNS topic for SES events.
4. HTTPS SNS subscription to `/anymail/amazon_ses/tracking/`.
5. Bounce and complaint webhook testing.
6. CloudWatch alarms for SES reputation.

When Novena is publicly hosted, revisit this guide and add:

```env
AWS_SES_CONFIGURATION_SET_NAME="novena-prod-email"
ANYMAIL_WEBHOOK_SECRET="<username>:<strong-password>"
```

Then subscribe SNS to:

```text
https://<username>:<strong-password>@<your-novena-domain>/anymail/amazon_ses/tracking/
```

## Troubleshooting

- `MessageRejected`: sender identity is not verified, SES is still in sandbox mode, or the recipient is not verified.
- `InvalidClientTokenId` or `SignatureDoesNotMatch`: AWS access key or secret key is incorrect.
- `AccessDenied`: IAM policy does not allow `ses:SendEmail` or `ses:SendRawEmail`.
- `ConfigurationSetDoesNotExist`: clear `AWS_SES_CONFIGURATION_SET_NAME` or create that configuration set in the selected SES region.
- Alert email does not send: restart Celery after changing `.env`, and confirm the alert rule has at least one email recipient.
- Email audit does not move past `sent`: expected during local-only development without SNS event publishing.

## References

- Anymail Amazon SES backend: https://anymail.dev/en/v13.0/esps/amazon_ses/
- AWS SES identity verification: https://docs.aws.amazon.com/ses/latest/dg/creating-identities.html
- AWS SES sandbox: https://docs.aws.amazon.com/ses/latest/dg/request-production-access.html
- AWS SES event publishing for later production setup: https://docs.aws.amazon.com/ses/latest/dg/monitor-using-event-publishing.html
