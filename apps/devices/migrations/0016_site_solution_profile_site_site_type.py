from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("devices", "0015_gateway_edge_diagnostics"),
    ]

    operations = [
        migrations.AddField(
            model_name="site",
            name="solution_profile",
            field=models.CharField(
                choices=[
                    ("general_iot", "General IoT"),
                    ("cold_chain", "Cold Chain Monitoring"),
                    ("factory_energy", "Factory Energy Monitoring"),
                    ("facilities_hvac", "Facilities / HVAC"),
                ],
                default="general_iot",
                help_text="UX preset for onboarding, dashboards, alerts, and reports.",
                max_length=30,
            ),
        ),
        migrations.AddField(
            model_name="site",
            name="site_type",
            field=models.CharField(
                blank=True,
                help_text="Optional profile-specific site type, such as hotel, clinic, or warehouse.",
                max_length=50,
            ),
        ),
    ]
