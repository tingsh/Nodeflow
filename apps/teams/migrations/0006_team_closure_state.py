from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("teams", "0005_alter_invitation_role_alter_membership_role"),
    ]

    operations = [
        migrations.AddField(
            model_name="team",
            name="closed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="team",
            name="closed_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="closed_teams",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="team",
            name="closed_reason",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
        migrations.AddField(
            model_name="team",
            name="status",
            field=models.CharField(
                choices=[("active", "Active"), ("closed", "Closed")],
                default="active",
                max_length=20,
            ),
        ),
    ]
