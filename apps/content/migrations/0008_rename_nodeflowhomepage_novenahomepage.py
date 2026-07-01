from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("content", "0007_auto_create_wagtail_pages"),
    ]

    operations = [
        migrations.RenameModel(
            old_name="NodeflowHomePage",
            new_name="NovenaHomePage",
        ),
    ]
