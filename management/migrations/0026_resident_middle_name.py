from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("management", "0025_resident_barangay_city_province"),
    ]

    operations = [
        migrations.AddField(
            model_name="resident",
            name="middle_name",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
    ]
