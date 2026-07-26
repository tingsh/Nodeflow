from django.apps import AppConfig


class ImpactConfig(AppConfig):
    default_auto_field = "django.db.models.AutoField"
    name = "apps.impact"
    verbose_name = "Business Impact"

    def ready(self):
        from . import signals  # noqa: F401
