from django.db import migrations, models


def rename_fee_types(apps, schema_editor):
    FeeType = apps.get_model("management", "FeeType")
    renames = {
        "Missed Meetings": "Penalty for Missed Meeting",
        "Missed Cleaning": "Penalty for Missed Cleaning",
    }
    for old_name, new_name in renames.items():
        fee_type = FeeType.objects.filter(name=old_name).first()
        if fee_type:
            fee_type.name = new_name
            fee_type.save(update_fields=["name"])
        else:
            FeeType.objects.get_or_create(name=new_name)


def revert_fee_types(apps, schema_editor):
    FeeType = apps.get_model("management", "FeeType")
    renames = {
        "Penalty for Missed Meeting": "Missed Meetings",
        "Penalty for Missed Cleaning": "Missed Cleaning",
    }
    for old_name, new_name in renames.items():
        fee_type = FeeType.objects.filter(name=old_name).first()
        if fee_type:
            fee_type.name = new_name
            fee_type.save(update_fields=["name"])


class Migration(migrations.Migration):

    dependencies = [
        ("management", "0012_add_missed_fee_types"),
    ]

    operations = [
        migrations.AlterField(
            model_name="feetype",
            name="name",
            field=models.CharField(max_length=50, unique=True),
        ),
        migrations.RunPython(rename_fee_types, revert_fee_types),
    ]
