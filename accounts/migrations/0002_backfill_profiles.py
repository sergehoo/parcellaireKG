"""Crée un profil pour chaque utilisateur existant (backfill additif, idempotent)."""
from django.conf import settings
from django.db import migrations


def create_profiles(apps, schema_editor):
    User = apps.get_model(*settings.AUTH_USER_MODEL.split("."))
    Profile = apps.get_model("accounts", "Profile")
    existing = set(Profile.objects.values_list("user_id", flat=True))
    to_create = [
        Profile(user_id=uid)
        for uid in User.objects.exclude(id__in=existing).values_list("id", flat=True)
    ]
    if to_create:
        Profile.objects.bulk_create(to_create)


class Migration(migrations.Migration):
    dependencies = [("accounts", "0001_initial")]
    operations = [migrations.RunPython(create_profiles, migrations.RunPython.noop)]
