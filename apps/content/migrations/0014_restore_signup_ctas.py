from django.db import migrations


SIGNUP_URL = "/accounts/signup/"


def _plain(value):
    if isinstance(value, dict):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    if hasattr(value, "items"):
        return {key: _plain(item) for key, item in value.items()}
    if not isinstance(value, (str, bytes)) and hasattr(value, "__iter__"):
        return [_plain(item) for item in value]
    return value


def _replace_homepage_ctas(blocks):
    updated = []
    for block in blocks or []:
        if hasattr(block, "block_type"):
            block_type = block.block_type
            value = _plain(block.value or {})
        else:
            block_type = block.get("type")
            value = _plain(block.get("value") or {})

        if block_type == "final_cta":
            if value.get("primary_cta_text") in {"Book a demo", "Book demo"}:
                value["primary_cta_text"] = "Sign up"
            if value.get("primary_cta_url") == "/about/#contact":
                value["primary_cta_url"] = SIGNUP_URL
        updated.append({"type": block_type, "value": value})
    return updated


def restore_signup_ctas(apps, schema_editor):
    NovenaHomePage = apps.get_model("content", "NovenaHomePage")

    for page in NovenaHomePage.objects.all():
        page.hero_cta_text = "Sign up"
        page.hero_cta_url = SIGNUP_URL
        page.body = _replace_homepage_ctas(page.body)
        page.save(update_fields=["hero_cta_text", "hero_cta_url", "body"])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("content", "0013_alter_marketingstandardpage_body_and_more"),
    ]

    operations = [
        migrations.RunPython(restore_signup_ctas, noop_reverse),
    ]
