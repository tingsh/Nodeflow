from .models import ActivityLog

def log_event(category, message, team, device=None, site=None, user=None, metadata=None):
    """
    Central utility to log system events.
    """
    return ActivityLog.objects.create(
        category=category,
        message=message,
        team=team,
        device=device,
        site=site,
        user=user,
        metadata=metadata or {}
    )
