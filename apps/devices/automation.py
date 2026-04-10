import logging
from apps.alerts.models import AlertRule

logger = logging.getLogger(__name__)

def apply_template_presets(device):
    """
    Automatically creates AlertRules for a device based on its template's alert_presets.
    """
    if not device.template or not device.template.alert_presets:
        return

    presets = device.template.alert_presets
    # Ensure presets is a list (JSONField default is list, but let's be safe)
    if not isinstance(presets, list):
        logger.warning(f"DeviceTemplate {device.template.id} has invalid alert_presets format.")
        return

    created_count = 0
    for preset in presets:
        try:
            # Check if an identical rule already exists to avoid duplicates
            rule, created = AlertRule.objects.get_or_create(
                team=device.team,
                device=device,
                telemetry_key=preset['key'],
                condition=preset['condition'],
                threshold=preset['threshold'],
                defaults={
                    'name': f"Auto: {device.name} {preset['key']} {preset['condition']} {preset['threshold']}",
                    'severity': preset.get('severity', 'warning'),
                    'site': device.site,
                    'is_active': True,
                }
            )
            if created:
                created_count += 1
        except Exception as e:
            logger.error(f"Error applying alert preset for device {device.id}: {e}")

    logger.info(f"Applied {created_count} alert presets to device {device.id} ({device.name})")
    return created_count
