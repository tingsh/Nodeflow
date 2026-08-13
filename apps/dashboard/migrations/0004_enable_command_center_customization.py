from django.db import migrations


def enable_command_center_customization(apps, schema_editor):
    flag_model = apps.get_model("teams", "Flag")
    flag_model.objects.update_or_create(
        name="command_center_customization",
        defaults={"everyone": True},
    )


class Migration(migrations.Migration):
    dependencies = [
        ("dashboard", "0003_commandcenterlayout"),
    ]

    operations = [
        migrations.RunPython(enable_command_center_customization, migrations.RunPython.noop),
    ]
