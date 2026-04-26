from django.db import migrations


def seed_fee_types(apps, schema_editor):
    FeeType = apps.get_model("management", "FeeType")
    for name in ["Missed Meetings", "Missed Cleaning"]:
        FeeType.objects.get_or_create(name=name)


def unseed_fee_types(apps, schema_editor):
    FeeType = apps.get_model("management", "FeeType")
    FeeType.objects.filter(name__in=["Missed Meetings", "Missed Cleaning"]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("management", "0011_paymenttransaction"),
    ]

    operations = [
        migrations.RunPython(seed_fee_types, unseed_fee_types),
    ]
