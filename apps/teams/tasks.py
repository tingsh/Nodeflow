import logging

from celery import shared_task
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.translation import gettext_lazy as _

from apps.events.models import EmailDelivery
from apps.events.services import TrackedEmailDeliveryError, send_tracked_email
from apps.users.models import CustomUser

from .models import Invitation

logger = logging.getLogger("novena_hub")


def _retry_countdown(retries):
    return min(300, 30 * (2**retries))


@shared_task(bind=True, max_retries=3)
def send_invitation_email_task(self, invitation_id):
    try:
        invitation = Invitation.objects.select_related("team", "invited_by").get(id=invitation_id)
    except Invitation.DoesNotExist:
        logger.error("Invitation %s not found for email dispatch.", invitation_id)
        return

    project_name = settings.PROJECT_METADATA["NAME"]
    email_context = {
        "invitation": invitation,
        "project_name": project_name,
    }
    recipient_user = CustomUser.objects.filter(email__iexact=invitation.email).first()
    user_by_email = {invitation.email.lower(): recipient_user} if recipient_user else {}

    try:
        send_tracked_email(
            team=invitation.team,
            notification_type=EmailDelivery.NotificationType.TEAM_INVITATION,
            subject=_("You're invited to {}!").format(project_name),
            text_body=render_to_string("teams/email/invitation.txt", context=email_context),
            html_body=render_to_string("teams/email/invitation.html", context=email_context),
            recipients=[invitation.email],
            from_email=settings.DEFAULT_FROM_EMAIL,
            invitation=invitation,
            user_by_email=user_by_email,
            metadata={"invitation_id": str(invitation.id), "team_id": invitation.team_id},
        )
        logger.info("Queued team invitation email delivery for invitation %s.", invitation.id)
    except TrackedEmailDeliveryError as exc:
        logger.warning(
            "Invitation email delivery failed for invitation %s on attempt %s/%s.",
            invitation.id,
            self.request.retries + 1,
            self.max_retries + 1,
        )
        raise self.retry(exc=exc, countdown=_retry_countdown(self.request.retries)) from exc
