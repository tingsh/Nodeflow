from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver

from .models import MaintenanceTicket
from .services import send_ticket_assignment_whatsapp, send_ticket_assignment_email


@receiver(pre_save, sender=MaintenanceTicket)
def ticket_pre_save(sender, instance, **kwargs):
    """
    Checks if the assignee has changed before saving the ticket.
    """
    if instance.id:
        try:
            old_instance = MaintenanceTicket.objects.get(id=instance.id)
            instance._assignee_changed = old_instance.assigned_to != instance.assigned_to
        except MaintenanceTicket.DoesNotExist:
            instance._assignee_changed = True
    else:
        instance._assignee_changed = True


@receiver(post_save, sender=MaintenanceTicket)
def ticket_post_save(sender, instance, created, **kwargs):
    """
    Triggers assignee notifications on assignment change.
    """
    if getattr(instance, "_assignee_changed", False) and instance.assigned_to:
        if instance.send_whatsapp_notification:
            send_ticket_assignment_whatsapp(instance)
        if instance.send_email_notification:
            send_ticket_assignment_email(instance)
