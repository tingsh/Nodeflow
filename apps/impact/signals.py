from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import ImpactReport
from .reporting import delete_private_report_file


@receiver(post_delete, sender=ImpactReport)
def delete_impact_report_file(sender, instance, **kwargs):
    transaction.on_commit(lambda: delete_private_report_file(instance))


@receiver(post_save, sender="devices.Site")
def create_site_impact_profile(sender, instance, created, **kwargs):
    if not created:
        return
    from .services import ensure_site_profile

    ensure_site_profile(instance)
