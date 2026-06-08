from django.db import migrations


def seed_prices(apps, schema_editor):
    Price = apps.get_model("billing", "Price")
    Price.objects.update_or_create(
        name="Gnome",
        amount_dollars=5,
        interval="month",
        defaults={"stripe_price_id": "", "active": True},
    )
    Price.objects.update_or_create(
        name="Gnome",
        amount_dollars=50,
        interval="year",
        defaults={"stripe_price_id": "", "active": True},
    )


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0002_price_delete_plan"),
    ]

    operations = [
        migrations.RunPython(seed_prices, migrations.RunPython.noop),
    ]
