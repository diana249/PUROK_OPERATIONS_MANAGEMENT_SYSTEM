from django.db import migrations


def forwards(apps, schema_editor):
    ClearanceType = apps.get_model("management", "ClearanceType")
    PurokClearance = apps.get_model("management", "PurokClearance")

    barangay = ClearanceType.objects.filter(name="Barangay").first()
    if barangay is None:
        return

    purok, _ = ClearanceType.objects.get_or_create(name="Purok Clearance")
    PurokClearance.objects.filter(clearance_type_id=barangay.id).update(clearance_type_id=purok.id)
    barangay.delete()


def backwards(apps, schema_editor):
    # No-op: we don't want to recreate Barangay automatically.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("management", "0016_merge_clearancetype_barangay_into_purok"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
