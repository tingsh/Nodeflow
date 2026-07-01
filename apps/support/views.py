import logging
from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import user_passes_test, login_required
from django.shortcuts import render
from django.core.mail import send_mail
from django.http import HttpResponse
from django.views.decorators.http import require_POST
from django.utils.translation import gettext as _

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
        return HttpResponse('<div class="alert alert-error font-bold rounded-2xl py-2 px-4 text-xs text-error-content mb-4">Message body cannot be empty!</div>', status=400)

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
        send_mail(
            subject=email_subject,
            message=email_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[support_email],
            fail_silently=False,
        )
        logger.info(f"Support email successfully sent to {support_email} from {user.email}")
        return render(request, "support/contact_success.html")
    except Exception as e:
        logger.error(f"Failed to send support email: {e}")
        return HttpResponse('<div class="alert alert-error font-bold rounded-2xl py-2 px-4 text-xs text-error-content mb-4">Failed to deliver message. Please try again later.</div>', status=500)

