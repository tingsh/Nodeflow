from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0004_customuser_department_customuser_job_title"),
    ]

    operations = [
        migrations.AddField(
            model_name="customuser",
            name="closed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="customuser",
            name="closed_reason",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
        migrations.AddField(
            model_name="customuser",
            name="original_email_hash",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
    ]
