from django.db import migrations


def forwards(apps, schema_editor):
    ClearanceType = apps.get_model("management", "ClearanceType")
    obj = ClearanceType.objects.filter(name="Barangay").first()
    if obj:
        obj.name = "Purok Clearance"
        obj.save(update_fields=["name"])
    else:
        ClearanceType.objects.get_or_create(name="Purok Clearance")


def backwards(apps, schema_editor):
    ClearanceType = apps.get_model("management", "ClearanceType")
    obj = ClearanceType.objects.filter(name="Purok Clearance").first()
    if obj:
        obj.name = "Barangay"
        obj.save(update_fields=["name"])


class Migration(migrations.Migration):

    dependencies = [
        ("management", "0014_attendance_attendance_type"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
