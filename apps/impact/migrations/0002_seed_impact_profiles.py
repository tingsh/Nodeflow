from django.db import migrations
from django.utils import timezone


SUPPORTED_PROFILES = {"factory_energy", "cold_chain", "facilities_hvac"}


def seed_impact_profiles(apps, schema_editor):
    Team = apps.get_model("teams", "Team")
    Site = apps.get_model("devices", "Site")
    BusinessImpactProfile = apps.get_model("impact", "BusinessImpactProfile")
    SiteImpactProfile = apps.get_model("impact", "SiteImpactProfile")
    ImpactAssumptionRevision = apps.get_model("impact", "ImpactAssumptionRevision")

    for team in Team.objects.iterator():
        business, _ = BusinessImpactProfile.objects.get_or_create(
            team_id=team.id,
            defaults={
                "currency": "SGD",
                "roi_start_date": timezone.localdate(),
            },
        )
        for site in Site.objects.filter(team_id=team.id).iterator():
            site_profile, _ = SiteImpactProfile.objects.get_or_create(
                team_id=team.id,
                site_id=site.id,
                defaults={
                    "vertical_profile": site.solution_profile,
                    "enabled": site.solution_profile in SUPPORTED_PROFILES,
                },
            )
            ImpactAssumptionRevision.objects.get_or_create(
                team_id=team.id,
                site_profile_id=site_profile.id,
                revision=1,
                defaults={"currency": business.currency},
            )


class Migration(migrations.Migration):
    dependencies = [
        ("impact", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_impact_profiles, migrations.RunPython.noop),
    ]
