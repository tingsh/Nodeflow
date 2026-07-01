from django.contrib import messages
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.core.mail import send_mail
from django.conf import settings

from .models import MaintenanceTicket, SharedTicketLink, TicketComment
from .forms import TicketCommentForm


def get_active_shared_link_or_none(token):
    try:
        link = SharedTicketLink.objects.get(token=token)
        if not link.is_active or link.is_expired:
            return None
        return link
    except SharedTicketLink.DoesNotExist:
        return None


def public_ticket_view(request, token):
    link = get_active_shared_link_or_none(token)
    if not link:
        return render(request, "maintenance/public/link_expired.html", status=404)

    # Record view stats
    if request.method == "GET":
        link.view_count += 1
        link.last_viewed_at = timezone.now()
        link.save(update_fields=["view_count", "last_viewed_at"])

    ticket = link.ticket
    comments = ticket.comments.order_by("created_at")
    comment_form = TicketCommentForm()

    context = {
        "link": link,
        "ticket": ticket,
        "comments": comments,
        "comment_form": comment_form,
    }
    return render(request, "maintenance/public/public_ticket_detail.html", context)


@require_POST
def public_toggle_checklist_item(request, token, item_index):
    link = get_active_shared_link_or_none(token)
    if not link:
        return HttpResponse("Link expired or inactive.", status=404)

    ticket = link.ticket
    try:
        checklist = list(ticket.checklist_state)
        if 0 <= item_index < len(checklist):
            item = checklist[item_index]
            item["done"] = not item.get("done", False)
            ticket.checklist_state = checklist
            ticket.save()

            # Create system comment for audit log
            state_label = "completed" if item["done"] else "incomplete"
            TicketComment.objects.create(
                team=link.team,
                ticket=ticket,
                author=None,
                content=f"Marked task '{item['task']}' as {state_label} (via Shareable Link).",
                is_system_generated=True
            )

            # Return updated public checklist partial
            return render(request, "maintenance/partials/public_checklist.html", {"ticket": ticket, "link": link})
    except Exception as e:
        return HttpResponse(str(e), status=400)

    return HttpResponse("Invalid request", status=400)


@require_POST
def public_add_comment(request, token):
    link = get_active_shared_link_or_none(token)
    if not link:
        return render(request, "maintenance/public/link_expired.html", status=404)

    form = TicketCommentForm(request.POST, request.FILES)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.ticket = link.ticket
        comment.team = link.team
        comment.author = None
        if not comment.guest_name:
            comment.guest_name = "External Contractor"
        comment.save()
        messages.success(request, "Comment and files uploaded successfully.")
    else:
        # Pass form errors through message
        for error_list in form.errors.values():
            for error in error_list:
                messages.error(request, error)

    return redirect("maintenance_public:public_ticket_view", token=token)


@require_POST
def public_update_status(request, token):
    link = get_active_shared_link_or_none(token)
    if not link:
        return render(request, "maintenance/public/link_expired.html", status=404)

    ticket = link.ticket
    new_status = request.POST.get("status")

    if new_status in MaintenanceTicket.StatusChoices.values:
        # Check compliance constraints if marking resolved or closed
        if new_status in [MaintenanceTicket.StatusChoices.RESOLVED, MaintenanceTicket.StatusChoices.CLOSED]:
            checklist = ticket.checklist_state or []
            incomplete_required = [item["task"] for item in checklist if item.get("required") and not item.get("done")]
            if incomplete_required:
                messages.error(
                    request, 
                    f"Cannot update status. The following required tasks must be completed first: {', '.join(incomplete_required)}"
                )
                return redirect("maintenance_public:public_ticket_view", token=token)

        old_status = ticket.get_status_display()
        ticket.status = new_status
        ticket.save()

        # Audit comment
        TicketComment.objects.create(
            team=link.team,
            ticket=ticket,
            author=None,
            content=f"Changed status from '{old_status}' to '{ticket.get_status_display()}' (via Shareable Link).",
            is_system_generated=True
        )

        # Notify manager if resolved
        if new_status == MaintenanceTicket.StatusChoices.RESOLVED and ticket.reported_by:
            send_manager_resolution_email(ticket)

        messages.success(request, f"Ticket status updated to {ticket.get_status_display()}.")

        # Handle auto-revocation
        if link.auto_revoke_on_resolve and new_status in [MaintenanceTicket.StatusChoices.RESOLVED, MaintenanceTicket.StatusChoices.CLOSED]:
            link.is_active = False
            link.save()

    return redirect("maintenance_public:public_ticket_view", token=token)


def send_manager_resolution_email(ticket):
    """Sends an email alert to the reporting manager when a ticket is resolved by a contractor."""
    if not ticket.reported_by or not ticket.reported_by.email:
        return
        
    subject = f"[Novena] Compliance Ticket Resolved: TKT-{ticket.id}"
    body = (
        f"Hi {ticket.reported_by.get_display_name()},\n\n"
        f"The maintenance ticket TKT-{ticket.id} '{ticket.title}' for device '{ticket.device.name}' "
        f"has been marked as RESOLVED by the external contractor.\n\n"
        f"Please log in to your Novena dashboard to review checklist completion details and any "
        f"uploaded photo logsheets or certificates before closing the ticket.\n\n"
        f"Best regards,\n"
        f"Novena Compliance Bot"
    )
    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[ticket.reported_by.email],
            fail_silently=True
        )
    except Exception:
        pass
