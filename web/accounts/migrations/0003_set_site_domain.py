from django.db import migrations


def set_site_domain(apps, schema_editor):
    Site = apps.get_model("sites", "Site")
    Site.objects.update_or_create(
        pk=1,
        defaults={"domain": "linkgno.me", "name": "LinkGnome"},
    )


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_alter_blueskyaccount_user_alter_mastodonaccount_user_and_more"),
        ("sites", "0002_alter_domain_unique"),
    ]

    operations = [
        migrations.RunPython(set_site_domain, migrations.RunPython.noop),
    ]
