from django.db.models.signals import post_save
from django.dispatch import receiver

from .automation import apply_template_presets
from .models import Device


@receiver(post_save, sender=Device)
def auto_configure_device(sender, instance, created, **kwargs):
    """
    Trigger automation logic when a new device is created.
    """
    if created:
        apply_template_presets(instance)
