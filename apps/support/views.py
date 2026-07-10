import logging

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from apps.events.models import EmailDelivery
from apps.events.services import TrackedEmailDeliveryError, send_tracked_email

from .forms import HijackUserForm

logger = logging.getLogger("novena_hub")


@user_passes_test(lambda u: u.is_superuser, login_url="/404")
@staff_member_required
def hijack_user(request):
    form = HijackUserForm()
    return render(
        request,
        "support/hijack_user.html",
        {
            "active_tab": "support",
            "form": form,
            "redirect_url": settings.LOGIN_REDIRECT_URL,
        },
    )


@login_required
@require_POST
def contact_support(request):
    category = request.POST.get("category", "General Inquiry")
    subject = request.POST.get("subject", "").strip()
    message = request.POST.get("message", "").strip()

    if not message:
        return HttpResponse(
            '<div class="alert alert-error font-bold rounded-2xl py-2 px-4 text-xs text-error-content mb-4">'
            "Message body cannot be empty!</div>",
            status=400,
        )

    user = request.user
    team_name = request.team.name if getattr(request, "team", None) else "No Team"
    email_subject = f"[Novena Support] {category}: {subject or 'No Subject'}"
    email_body = (
        f"Support Request Details:\n"
        f"------------------------\n"
        f"User: {user.get_display_name()} ({user.email})\n"
        f"Team: {team_name}\n"
        f"Category: {category}\n"
        f"Subject: {subject}\n\n"
        f"Message:\n"
        f"------------------------\n"
        f"{message}\n"
    )

    support_email = settings.PROJECT_METADATA.get("CONTACT_EMAIL", settings.DEFAULT_FROM_EMAIL)

    try:
        send_tracked_email(
            team=getattr(request, "team", None),
            notification_type=EmailDelivery.NotificationType.SUPPORT_REQUEST,
            subject=email_subject,
            text_body=email_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipients=[support_email],
            user_by_email={user.email.lower(): user} if user.email else {},
            metadata={"category": category, "request_user_id": user.id},
        )
        logger.info(f"Support email successfully sent to {support_email} from {user.email}")
        return render(request, "support/contact_success.html")
    except TrackedEmailDeliveryError as e:
        logger.error(f"Failed to send support email: {e}")
        return HttpResponse(
            '<div class="alert alert-error font-bold rounded-2xl py-2 px-4 text-xs text-error-content mb-4">'
            "Failed to deliver message. Please try again later.</div>",
            status=500,
        )


@require_POST
def sales_inquiry(request):
    if request.POST.get("company_website"):
        return render(request, "support/sales_success.html", {"quiet": True})

    name = request.POST.get("name", "").strip()
    email = request.POST.get("email", "").strip()
    company = request.POST.get("company", "").strip()
    interest = request.POST.get("interest", "General demo request").strip()
    message = request.POST.get("message", "").strip()

    if not all([name, email, company, message]):
        return HttpResponse(
            '<div class="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm font-semibold '
            'text-red-700">Please complete all required fields.</div>',
            status=400,
        )

    try:
        validate_email(email)
    except ValidationError:
        return HttpResponse(
            '<div class="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm font-semibold '
            'text-red-700">Please enter a valid work email.</div>',
            status=400,
        )

    support_email = settings.PROJECT_METADATA.get("CONTACT_EMAIL", settings.DEFAULT_FROM_EMAIL)
    email_subject = f"[Novena Sales] {interest}: {company}"
    email_body = (
        "Public demo request\n"
        "-------------------\n"
        f"Name: {name}\n"
        f"Email: {email}\n"
        f"Company: {company}\n"
        f"Interest: {interest}\n\n"
        "Message\n"
        "-------\n"
        f"{message}\n"
    )

    try:
        send_tracked_email(
            team=None,
            notification_type=EmailDelivery.NotificationType.SALES_INQUIRY,
            subject=email_subject,
            text_body=email_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipients=[support_email],
            metadata={"sender_email": email, "company": company, "interest": interest},
        )
        logger.info("Sales inquiry sent to %s from %s", support_email, email)
        return render(request, "support/sales_success.html")
    except TrackedEmailDeliveryError as e:
        logger.error("Failed to send sales inquiry email: %s", e)
        return HttpResponse(
            '<div class="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm font-semibold '
            'text-red-700">We could not send the request. Please email us directly and try again later.</div>',
            status=500,
        )
