from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("management", "0013_rename_missed_fee_types"),
    ]

    operations = [
        migrations.AddField(
            model_name="attendance",
            name="attendance_type",
            field=models.CharField(choices=[("Meeting", "Meeting"), ("Cleaning", "Cleaning")], default="Meeting", max_length=20),
        ),
        migrations.AddIndex(
            model_name="attendance",
            index=models.Index(fields=["attendance_type"], name="management_a_attenda_a13c6c_idx"),
        ),
    ]
