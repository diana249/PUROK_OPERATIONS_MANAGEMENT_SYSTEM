from django.db import migrations


def forwards(apps, schema_editor):
    ClearanceType = apps.get_model("management", "ClearanceType")
    PurokClearance = apps.get_model("management", "PurokClearance")

    barangay = ClearanceType.objects.filter(name="Barangay").first()
    purok, _ = ClearanceType.objects.get_or_create(name="Purok Clearance")

    if barangay is None:
        return

    # Move any existing records to the new type, then remove the old type.
    PurokClearance.objects.filter(clearance_type_id=barangay.id).update(clearance_type_id=purok.id)
    barangay.delete()


def backwards(apps, schema_editor):
    ClearanceType = apps.get_model("management", "ClearanceType")
    PurokClearance = apps.get_model("management", "PurokClearance")

    purok = ClearanceType.objects.filter(name="Purok Clearance").first()
    barangay, _ = ClearanceType.objects.get_or_create(name="Barangay")

    if purok is None:
        return

    # Best-effort: move records back.
    PurokClearance.objects.filter(clearance_type_id=purok.id).update(clearance_type_id=barangay.id)


class Migration(migrations.Migration):

    dependencies = [
        ("management", "0015_rename_clearancetype_barangay"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
